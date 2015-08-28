#!/usr/bin/python3

import os,random,sys

try :
         from dd_amqp         import *
         from dd_config       import *
         from dd_message      import *
         from dd_util         import *
except :
         from sara.dd_amqp    import *
         from sara.dd_config  import *
         from sara.dd_message import *
         from sara.dd_util    import *

class dd_post(dd_config):

    def __init__(self,config=None,args=None):
        dd_config.__init__(self,config,args)
        self.configure()

    def check(self):

        if self.source == None :
           self.logger.error("source required")
           sys.exit(1)

        self.chkclass = Checksum()
        self.chkclass.from_list(self.sumflg)
        self.chksum = self.chkclass.checksum

        self.exchange_name  = 'sx_' + self.post_broker.username
        if self.post_exchange != None :
           self.exchange_name = self.post_exchange

        self.msg = dd_message(self.logger)
        self.msg.set_exchange_name(self.exchange_name)
        self.msg.set_post_exchange_topic_key(self.post_broker.username,self.source,self.post_topic)
        self.msg.set_post_options(self.flow,self.rename,'IN_CLOSE_WRITE')


    def close(self):
        self.hc_post.close()

    def connect(self):

        self.hc_post      = HostConnect( logger = self.logger )
        self.hc_post.set_url( self.post_broker )

        # dd_post : no loop to reconnect to broker

        if self.program_name == 'dd_post' :
           self.hc_post.loop = False
                                   
        self.hc_post.connect()

        self.pub    = Publisher(self.hc_post)
        self.pub.build()

        ex = Exchange(self.hc_post,self.exchange_name)
        ex.build()

    def help(self):
        self.logger.info("Usage: %s -s <source-url> -pb <broker-url> ... [OPTIONS]\n" % self.program_name )
        self.logger.info("OPTIONS:")
        self.logger.info("-c   <config_file>")
        self.logger.info("-dr  <document_root>")
        if self.program_name == 'dd_watch' : self.logger.info("-e   <events>\n")
        self.logger.info("-f   <flow>\n")
        self.logger.info("-l   <logpath>")
        self.logger.info("-p   <parts>")
        self.logger.info("-pe  <exchange>")
        self.logger.info("-pt  <post_topic>")
        self.logger.info("-pk  <post_topic_key>")
        self.logger.info("-rn  <rename>")
        self.logger.info("-sum <sum>")
        self.logger.info("DEBUG:")
        self.logger.info("-debug")
        self.logger.info("-r  : randomize chunk posting")
        self.logger.info("-rr : reconnect between chunks")

    def instantiate(self,i=0):
        self.instance = i
        self.setlog()

    def posting(self):

        filepath = self.source.path[1:]

        # check abspath for filename

        if self.document_root != None :
           if not self.document_root in filepath :
              filepath = self.document_root + os.sep + filepath

        # verify that file exists

        if not os.path.isfile(filepath) and self.event != 'IN_DELETE' :
           self.logger.error("File not found %s " % filepath )
           return False

        # rename path given with no filename

        if self.rename != None and self.rename[-1] == os.sep :
           self.rename += os.path.basename(self.source.path)

        # ==============
        # Chunk set up
        # ==============

        N = 1
        if self.event == 'IN_CLOSE_WRITE' :
           chunk  = Chunk(self.blocksize,self.chksum,filepath)
           N      = chunk.get_Nblock()

        # ==============
        # Randomize
        # ==============

        rparts = list(range(0,N))

        # randomize chunks
        if self.randomize and N>1 :
           i = 0
           while i < N/2+1 :
               j         = random.randint(0,N-1)
               tmp       = rparts[j]
               rparts[j] = rparts[i]
               rparts[i] = tmp
               i = i + 1

        # ==============
        # loop on chunk
        # ==============

        self.logger.debug("vhost %s  exchange_name %s" % (self.post_broker.path,self.exchange_name) )

        i  = 0
        while i < N:

            # build message
 
            if self.event == 'IN_CLOSE_WRITE' :
               c = chunk.get( rparts[i] )
               blocksize, block_count, remainder, current_block, sum_data = c
               self.msg.set_post_parts(self.partflg, blocksize, block_count, remainder, current_block)
               self.msg.set_post_sum(self.sumflg,sum_data)
            if self.event == 'IN_DELETE' :
               self.msg.set_post_sum(None)
               self.msg.set_post_parts(None)
               self.msg.set_post_sum(None)

            self.msg.set_post_notice(self.source)
            self.msg.set_post_headers()

            self.logger.info("Key %s" % self.msg.exchange_topic_key )
            self.logger.info("Notice %s" % self.msg.notice)
            self.logger.info("parts=%s sum=%s flow=%s rename=%s event=%s" %(self.msg.partstr,self.msg.sumstr,self.msg.flow,self.msg.rename,self.msg.event))

            self.msg.print_message()

            # publish
            ok = self.pub.publish( self.msg.exchange_name, self.msg.exchange_topic_key, self.msg.notice, self.msg.headers )
            if not ok :
               sys.exit(1)
            self.logger.info("published")

            # reconnect ?
            if self.reconnect :
               self.logger.info("Reconnect")
               self.hc_post.reconnect()

            i = i + 1

    def watching(self, fpath, event ):

        self.event = event
        self.msg.set_post_options(self.flow,self.rename,self.event)

        if self.document_root != None :
           bd = self.document_root
           if self.document_root[-1] != '/' : bd = bd + '/'
           fpath = fpath.replace(bd,'')

        source = self.source
        self.source = urllib.parse.urlparse('%s://%s%s'%(source.scheme,source.netloc,fpath))
        self.msg.set_post_exchange_topic_key(self.post_broker.username,self.source,self.post_topic)
        self.posting()
        self.source = source

    def watchpath(self ):

       watch_path = self.source.path
       if watch_path == None : watch_path = ''

       if self.document_root != None :
          if not self.document_root in watch_path :
             watch_path = self.document_root + os.sep + watch_path

       if not os.path.exists(watch_path):
          self.logger.error("Not found %s " % watch_path )
          sys.exit(1)

       if os.path.isfile(watch_path):
          self.logger.info("Watching file %s " % watch_path )

       if os.path.isdir(watch_path):
          self.logger.info("Watching directory %s " % watch_path )

       return watch_path


# ===================================
# MAIN
# ===================================

def main():

    post = dd_post(config=None,args=sys.argv[1:])

    try :
             post.instantiate()
             post.connect()
             post.posting()
             post.close()
    except :
             (stype, value, tb) = sys.exc_info()
             post.logger.error("Type: %s, Value:%s\n" % (stype, value))
             sys.exit(1)


    sys.exit(0)

# =========================================
# direct invocation
# =========================================

if __name__=="__main__":
   main()

