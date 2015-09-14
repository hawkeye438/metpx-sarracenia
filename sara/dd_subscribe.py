#!/usr/bin/python3

import logging, logging.handlers, os, random, re, signal, string, sys, time, getopt
import amqplib.client_0_8 as amqp

try :
         from dd_transfert      import *
         from dd_util           import *
except :
         from sara.dd_transfert import *
         from sara.dd_util      import *

#============================================================
# usage example
#
# python dd_subscribe.py configfile.conf

#============================================================

#############################################################################################
# Class AlarmTimeout

class TimeoutException(Exception):
    """Classe d'exception specialises au timeout"""
    pass

class AlarmTimeout:
      def __init__(self, message ):
          self.state   = False
          self.message = message
      def sigalarm(self, n, f):
          raise TimeoutException(self.message)
      def alarm(self, time):
          self.state = True
          signal.signal(signal.SIGALRM, self.sigalarm)
          signal.alarm(time)
      def cancel(self):
          signal.alarm(0)
          self.state = False

#============================================================

class Consumer(object):

    def __init__(self,config,logger):
        self.logger     = logger

        self.connected  = False

        self.connection = None
        self.channel1   = None
        self.channel2   = None
        self.ssl        = False

        self.queue      = None
        self.durable    = False
        self.expire     = None

        self.notify_only = False
        self.discard = False
        
        self.config = config
        self.name   = config

        self.download = dd_download(self.logger)

        self.myinit()

        self.timex = None

        self.log = None

        self.recompute_chksum = False

    def ack(self,msg):
        # ack timeout 5 sec
        if self.timex != None:self.timex.alarm(5)
        self.channel1.basic_ack(msg.delivery_tag)
        if self.timex != None:self.timex.cancel()

    def close(self):
       # timeout 5 sec for each operation
       if self.timex != None:self.timex.alarm(5)
       try:    self.channel2.close()
       except: pass
       try:    self.channel1.close()
       except: pass
       if self.timex != None:self.timex.cancel()

       if self.timex != None:self.timex.alarm(5)
       try:    self.connection.close()
       except: pass
       if self.timex != None:self.timex.cancel()

       self.connected = False

    def connect(self):
        self.connection = None
        self.channel1   = None
        self.channel2   = None

        while True:
             # give 20 sec to connect
             if self.timex != None:self.timex.alarm(20)

             try:
                  # connect
                  host = self.host
                  if self.port != '5672' : host = host + ':' + self.port
                  self.logger.info("AMQP connecting %s %s " % (host,self.amqp_user) )
                  self.connection = amqp.Connection(host, userid=self.amqp_user,
                                                    password=self.amqp_passwd, ssl=self.ssl,connect_timeout=60)
                  self.channel1   = self.connection.channel()

                  # shared queue : each pull receive 1 message (prefetch_count=1)
                  self.channel1.basic_qos(prefetch_size=0,prefetch_count=1,a_global=False)

                  # queue declare and bind

                  args = None
                  if self.expire != None :
                     args = { 'x-expires' : self.expire }

                  qn,Nmsg,Nconsumer = self.channel1.queue_declare( self.queue,
                                      passive=False, durable=self.durable, exclusive=False,
                                      auto_delete=False, nowait=False, arguments=args )

                  for k in self.exchange_key :
                      self.logger.info('Binding %s to %s with %s', self.exchange, self.queue, k)
                      self.channel1.queue_bind(self.queue, self.exchange, k )

                  # logging
                  self.channel2   = self.connection.channel()
                  self.channel2.tx_select()

                  if self.timex != None:self.timex.cancel()
                  self.connected = True
                  self.logger.info("Connected ")

                  break
             except (KeyboardInterrupt, SystemExit):
                 break                      
             except:
                  if self.timex != None:self.timex.cancel()
                  (stype, value, tb) = sys.exc_info()
                  self.logger.error("AMQP Sender cannot connected to: %s" % str(self.host))
                  self.logger.error("Type: %s, Value: %s, Sleeping 5 seconds ..." % (stype, value))
                  time.sleep(5)


    def consume(self):

        # give 10 sec to consume a message
        if self.timex != None:self.timex.alarm(10)

        try :
              msg = self.channel1.basic_get(self.queue)
              if self.timex != None:self.timex.cancel()
        except :
              if self.timex != None:self.timex.cancel()
              msg = None
              time.sleep(5)
              self.reconnect()

        if msg == None : time.sleep(0.01)
        return msg

    def reconnect(self):
        self.close()
        self.connect()

    def run(self):

        if not self.connected : self.connect()

        while True :

             try  :
                  msg = self.consume()
                  if msg == None : continue

                  body = msg.body
                  hdr  = msg.properties['application_headers']

                  routing_key = msg.delivery_info['routing_key']
                  exchange    = msg.delivery_info['exchange']
                  filename    = hdr['filename']

                  self.logger.debug('Received message # %s from %s: %s', msg, msg.delivery_info, body)
                  self.logger.debug('Received exchange %s, key %s, message file %s', exchange, routing_key, filename )

                  if sys.version[:1] >= '3' and type(body) == bytes : body = body.decode("utf-8")

                  processed = self.treat_message(exchange,routing_key,body,filename)

                  if processed :
                     self.ack(msg)
             except (KeyboardInterrupt, SystemExit):
                 break                 
             except :
                 (stype, value, tb) = sys.exc_info()
                 self.logger.error("Type: %s, Value: %s,  ..." % (stype, value))
                 
                 

    def myinit(self):
        self.bufsize       = 128 * 1024     # read/write buffer size

        self.protocol      = 'amqp'
        self.host          = 'dd.weather.gc.ca'
        self.port          = '5672'
        self.amqp_user     = 'anonymous'
        self.amqp_passwd   = 'anonymous'
        self.masks         = []             # All the masks (accept and reject)
        self.lock          = '.tmp'         # file send with extension .tmp for lock

        self.exchange      = 'xpublic'
        self.exchange_type = 'topic'
        self.exchange_key  = []

        self.http_user     = None
        self.http_passwd   = None

        self.flatten       = '/'
        self.mirror        = False
        
        self.readConfig()

        self.download.user     = self.http_user
        self.download.password = self.http_passwd

        # if not set in config : automated queue name saved in queuefile

        if self.queue == None :
           self.queuefile = ''
           parts = self.config.split(os.sep)
           if len(parts) != 1 :  self.queuefile = os.sep.join(parts[:-1]) + os.sep

           fnp   = parts[-1].split('.')
           if fnp[0][0] != '.' : fnp[0] = '.' + fnp[0]
           self.queuefile = self.queuefile + '.'.join(fnp[:-1]) + '.queue'

           self.queuename()

    def queuename(self) :

        self.queue  = 'cmc'
        if sys.version[:1] >= '3' :
           self.queue += '.' + str(random.randint(0,100000000)).zfill(8)
           self.queue += '.' + str(random.randint(0,100000000)).zfill(8)
        else :
           self.queue += '.' + string.zfill(random.randint(0,100000000),8)
           self.queue += '.' + string.zfill(random.randint(0,100000000),8)

        if os.path.isfile(self.queuefile) :
           f = open(self.queuefile)
           self.queue = f.read()
           f.close()
        else :
           f = open(self.queuefile,'w')
           f.write(self.queue)
           f.close()


    # url path will be replicated under odir (the directory given in config file)
    def mirrorpath(self, odir, url ):
        nodir = odir
        
        try :
              parts = url.split("/")
              for d in parts[3:-1] :
                  nodir = nodir + os.sep + d
                  if os.path.isdir(nodir) : continue
                  os.mkdir(nodir)
        except :
              self.logger.error("could not create or use directory %s" % nodir)
              return None

        return nodir

       
    def publish(self,exchange_name,exchange_key,message,filename):
        try :
              hdr = {'filename': filename }
              msg = amqp.Message(message, content_type= 'text/plain',application_headers=hdr)
              self.channel2.basic_publish(msg, exchange_name, exchange_key )
              self.channel2.tx_commit()
              return True
        except :
              (stype, value, tb) = sys.exc_info()
              self.logger.error("Type: %s, Value: %s" % (stype, value))
              time.sleep(5)
              self.reconnect()
              return self.publish(exchange_name,exchange_key,message,filename)


    # process individual url notification
    def treat_message(self,exchange,routing_key,msg,filename):

        # in operational version, routing key starts with 'v**.dd.notify'
        # in that case message is  'md5sum http://hostname/ filepath'
        url = msg
        if routing_key[0] == 'v' :
           parts = msg.split()
           url   = parts[-2] + parts[-1]

        # root directory where the product will be put
        odir = self.getMatchingMask(url)

        # no root directory for this url means url not selected
        if not odir : return True
        
        # notify_only mode : print out received message
        if self.notify_only :
           self.logger.info("%s" % msg)
           return True
        
        # root directory should exists
        if not os.path.isdir(odir) :
           self.logger.error("directory %s does not exist" % odir)
           return False

        # mirror mode True
        # means extend root directory with url directory
        nodir = odir
        if self.mirror :
           nodir = self.mirrorpath(odir,url)
           if nodir == None : return False

        # filename setting
        parts = url.split("/")
        fname = parts[-1]

        # flatten mode True
        # means use url to create filename by replacing "/" for self.flatten character
        if self.flatten != '/' :
           fname = self.flatten.join(parts[3:])

        # setting filepath and temporary filepath
        opath = nodir + os.sep + fname
        tpath = opath + self.lock

        # special case where lock is only '.' ... it leads the filename
        if self.lock == '.' : tpath = nodir + os.sep + '.' + fname

        # download file        

        body    = msg
        str_key = routing_key

        # instanciate key and notice

        dkey    = Key()
        notice  = Notice()
        new_key = str_key

        if str_key[:3] == 'v01':
           dkey.from_key(str_key) 
           notice.from_notice(body)
        else :
           dkey.from_v00_key(str_key,self.amqp_user)
           notice.from_v00_notice(body)
           new_key = dkey.get()
           body    = notice.get()

        ok = True
        if notice.url[:4] != 'http' : ok = False

        if not ok :
           log_key = new_key.replace('.post.','.log.')
           self.logger.error('Not valid: %s',body)
           body   += ' 404 ' + socket.gethostname() + ' ' + self.source.user + ' 0.0'
           self.publish('log',log_key,body,filename)
           return True

        # Target file and directory (directory created if needed)

        #self.download(url,tpath,opath,self.http_user,self.http_passwd)

        dnotice = Notice()
        dnotice.from_notice(body)
       
        self.download.set_key(dkey)
        self.download.set_notice(dnotice)
        self.download.set_publish(None,self)
        self.download.set_recompute(self.recompute_chksum)

        self.download.set_url(notice.url)
        self.download.set_local_file(tpath)
        ok = self.download.get(notice.chunksize, notice.block_count, notice.remainder, notice.current_block, \
                               notice.str_flags,notice.data_sum)

        if not ok : return False
               
        #option to discard file
        if self.discard: 
           try:
               os.unlink(tpath)
               self.logger.info('Discard %s', tpath)
           except:
               self.logger.error('Unable to discard %s', tpath)
        else:
           os.rename(tpath,opath)                                        
           self.logger.info('Local file created: %s', opath)

        return True
                    

    def readConfig(self):
        currentDir = '.'
        currentFileOption = 'NONE' 
        self.readConfigFile(self.config,currentDir,currentFileOption)

    def readConfigFile(self,filePath,currentDir,currentFileOption):
        
        def isTrue(s):
            if  s == 'True' or s == 'true' or s == 'yes' or s == 'on' or \
                s == 'Yes' or s == 'YES' or s == 'TRUE' or s == 'ON' or \
                s == '1' or  s == 'On' :
                return True
            else:
                return False

        try:
            config = open(filePath, 'r')
        except:
            (stype, value, tb) = sys.exc_info()
            print("Type: %s, Value: %s" % (stype, value))
            return 

        self.timeout = 180

        for line in config.readlines():
            words = line.split()
            if (len(words) >= 2 and not re.compile('^[ \t]*#').search(line)):
                try:
                    if   words[0] == 'accept':
                         cmask       = re.compile(words[1])
                         cFileOption = currentFileOption
                         if len(words) > 2: cFileOption = words[2]
                         self.masks.append((words[1], currentDir, cFileOption, cmask, True))
                    elif words[0] == 'reject':
                         cmask = re.compile(words[1])
                         self.masks.append((words[1], currentDir, currentFileOption, cmask, False))
                    elif words[0] == 'directory': currentDir = words[1]
                    elif words[0] == 'protocol':
                         self.protocol = words[1]
                         if self.protocol == 'amqps' : self.ssl = True
                    elif words[0] == 'host': self.host = words[1]
                    elif words[0] == 'port': self.port = int(words[1])
                    elif words[0] == 'amqp-user': self.amqp_user = words[1]
                    elif words[0] == 'amqp-password': self.amqp_passwd = words[1]
                    elif words[0] == 'lock': self.lock = words[1]

                    elif words[0] == 'exchange': self.exchange = words[1]
                    elif words[0] == 'exchange_type': 
                         if words[1] in ['fanout','direct','topic','headers'] :
                            self.exchange_type = words[1]
                         else :
                            self.logger.error("Problem with exchange_type %s" % words[1])
                    elif words[0] == 'exchange_key': self.exchange_key.append(words[1])
                    elif words[0] == 'http-user': self.http_user = words[1]
                    elif words[0] == 'http-password': self.http_passwd = words[1]
                    elif words[0] == 'mirror': self.mirror = isTrue(words[1])
                    elif words[0] == 'flatten': self.flatten = words[1]
                    elif words[0] == 'timeout': self.timeout = int(words[1])

                    elif words[0] == 'durable': self.durable = isTrue(words[1])
                    elif words[0] == 'expire': self.expire = int(words[1]) * 60 * 1000
                    elif words[0] == 'queue': self.queue = words[1] 
                    else:
                        self.logger.error("Unknown configuration directive %s in %s" % (words[0], self.config))
                        print("Unknown configuration directive %s in %s" % (words[0], self.config))
                except:
                    self.logger.error("Problem with this line (%s) in configuration file of client %s" % (words, self.name))
        config.close()
    
    def getMatchingMask(self, filename): 
        for mask in self.masks:
            if mask[3].match(filename) != None :
               if mask[4] : return mask[1]
               return None
        return None

def help():     
    #print chr(27)+'[1m'+'Script'+chr(27)+'[0m'
    print("Usage: dd_subscribe [OPTION]...[CONFIG_FILE]")
    print("dd_subscribe [-n|--no-download] [-d|--download-and-discard] [-l|--log-dir] config-file")
    print("rabbitmq python client connects to rabbitmq server for getting notice in real time to download new files")
    print("Examples:")    
    print("dd_subscribe subscribe.conf  # download files and display log in stout")
    print("dd_subscribe -d subscribe.conf  # discard files after downloaded and display log in stout")
    print("dd_subscribe -l /tmp subscribe.conf  # download files,write log file in directory /tmp")
    print("dd_subscribe -n subscribe.conf  # get notice only, no file downloaded and display log in stout")        

def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    #print('Resume in 5 seconds...')
    #time.sleep(5)
    sys.exit()
    #os.kill(os.getpid(),9)

def verify_version():    
    python_version = (2,6,0)
    if sys.version_info < python_version :
        sys.stderr.write("Python version higher than 2.6.0 required.\n")
        exit(1)
        
    amqplib_version = '1.0.0'   
    if amqp.connection.LIBRARY_PROPERTIES['library_version'] < amqplib_version:
        sys.stderr.write("Amqplib version %s or higher required.\n" % amqplib_version)        
        exit(1)
    
def main():

    verify_version()
    signal.signal(signal.SIGINT, signal_handler)

    ldir = None
    notice_only = False
    discard = False
    config = None
    timex = None
    
    #get options arguments
    try:
      opts, args = getopt.getopt(sys.argv[1:],'hl:dtn',['help','log-dir=','download-and-discard','timeout','no-download'])
    except getopt.GetoptError as err:    
      print("Error 1: %s" %err)
      print("Try `dd_subscribe --help' for more information.")
      sys.exit(2)                    
    
    #validate options
    if opts == [] and args == []:
      help()  
      sys.exit(1)
    for o, a in opts:
      if o in ('-h','--help'):
        help()
        sys.exit(1)
      elif o in ('-n','--no-download'):
        notice_only = True        
      elif o in ('-l','--log-dir'):
        ldir = a       
        if not os.path.exists(ldir) :
          print("Error 2: specified logging directory does not exist.")
          print("Try `dd_subscribe --help' for more information.")
          sys.exit(2)
      elif o in ('-d','--download-and-discard'):
        discard = True        
        
    #validate arguments
    if len(args) == 1:
      config = args[0]
      if not os.path.exists(config) :
         print("Error 3: configuration file does not exist.")
         sys.exit(2)
    elif len(args) == 0:
      help()  
      sys.exit(1)
    else:      
      print("Error 4: too many arguments given: %s." %' '.join(args))
      print("Try `dd_subscribe --help' for more information.")
      sys.exit(2)            
             
    # logging to stdout
    LOG_FORMAT = ('%(asctime)s [%(levelname)s] %(message)s')

    if ldir == None :
       LOGGER = logging.getLogger(__name__)
       logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    # user wants to logging in a directory/file
    else :       
       fn     = config.replace(".conf","")
       lfn    = fn + "_%s" % os.getpid() + ".log"
       lfile  = ldir + os.sep + lfn

       # Standard error is redirected in the log
       sys.stderr = open(lfile, 'a')

       # python logging
       LOGGER = None
       fmt    = logging.Formatter( LOG_FORMAT )
       hdlr   = logging.handlers.TimedRotatingFileHandler(lfile, when='midnight', interval=1, backupCount=5) 
       hdlr.setFormatter(fmt)
       LOGGER = logging.getLogger(lfn)
       LOGGER.setLevel(logging.INFO)
       LOGGER.addHandler(hdlr)

    # instanciate consumer

    consumer = Consumer(config,LOGGER)
    consumer.notify_only = notice_only
    consumer.discard = discard
    consumer.timex = timex
    
    consumer.run()
    """
    while True:
         try:
                consumer.run()
         except :
                (stype, value, tb) = sys.exc_info()
                LOGGER.error("Type: %s, Value: %s,  ..." % (stype, value))
                time.sleep(10)
                pass
                
    """
    consumer.close()

# =========================================
# direct invocation
# =========================================

if __name__=="__main__":
   main()
