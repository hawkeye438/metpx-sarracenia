#!/usr/bin/python3
#
# This file is part of sarracenia.
# The sarracenia suite is Free and is proudly provided by the Government of Canada
# Copyright (C) Her Majesty The Queen in Right of Canada, Environment Canada, 2008-2015
#
# Questions or bugs report: dps-client@ec.gc.ca
# sarracenia repository: git://git.code.sf.net/p/metpx/git
# Documentation: http://metpx.sourceforge.net/#SaraDocumentation
#
# dd_subscribe.py : python3 program allowing users to download product from dd.weather.gc.ca
#                   as soon as they are made available (through amqp notifications)
#
#
# Code contributed by:
#  Michel Grenier - Shared Services Canada
#  Jun Hu         - Shared Services Canada
#  Last Changed   : Sep 22 10:41:32 EDT 2015
#  Last Revision  : Sep 22 10:41:32 EDT 2015
#
########################################################################
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, 
#  but WITHOUT ANY WARRANTY; without even the implied warranty of 
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
#

import signal

#============================================================
# usage example
#
# dd_log2clusters -b broker -i 1

#============================================================

try :    
         from dd_amqp           import *
         from dd_instances      import *
         from dd_message        import *
except : 
         from sara.dd_amqp      import *
         from sara.dd_instances import *
         from sara.dd_message   import *


class dd_log2clusters(dd_instances):

    def __init__(self,config=None,args=None):
        dd_instances.__init__(self,config,args)
        self.defaults()
        self.source_exchange = 'xlog'
        self.source_broker   = urllib.parse.urlparse('amqp://guest:guest@localhost/')
        self.source_topic    = 'v02.log.#'
        self.index           = 0
        self.configure()
        self.nbr_instances   = len(self.log_clusters)

    def check(self):
        # dont want to recreate these if they exists
        if not hasattr(self,'msg') :
           self.msg = dd_message(self.logger)

    def close(self):
        self.hc_src.close()
        self.hc_pst.close()

    def configure(self):

        # installation general configurations and settings

        self.general()

        # arguments from command line

        self.args(self.user_args)

        # config from file

        self.config(self.user_config)

        # verify all settings

        self.check()

        self.cluster, self.broker, self.exchange = self.log_clusters[self.index]

    def connect(self):

        # =============
        # consumer
        # =============

        # consumer host

        self.hc_src = HostConnect( logger = self.logger )
        self.hc_src.set_url( self.source_broker )
        self.hc_src.connect()

        # consumer  add_prefetch(1) allows queue sharing between instances

        self.consumer  = Consumer(self.hc_src)
        self.consumer.add_prefetch(1)
        self.consumer.build()

        # consumer queue

        name  = 'q_' + self.broker.username
        if self.queue_name != None :
           name += '.' + self.queue_name
        else :
           name += '.' + self.program_name
        name += '.' + self.broker.hostname + '.' + self.exchange

        self.queue = Queue(self.hc_src,name)
        self.queue.add_binding(self.source_exchange,self.source_topic)
        self.queue.build()

        # =============
        # publisher
        # =============

        # publisher host

        self.hc_pst = HostConnect( logger = self.logger )
        self.hc_pst.set_url( self.broker )
        self.hc_pst.connect()

        # publisher

        self.pub    = Publisher(self.hc_pst)
        self.pub.build()

    def help(self):
        self.logger.info("Usage: %s -b <broker> [start|stop|restart|reload|status]  \n" % self.program_name )
        self.logger.info("OPTIONS:")
        self.logger.info("-b   <broker>    default:amqp://guest:guest@localhost/")

    def run(self):

        self.logger.info("dd_log2clusters run")
        self.logger.info("checking for %s" % self.cluster)

        self.connect()

        self.msg.logger       = self.logger

        #
        # loop on all message
        #

        raw_msg = None

        while True :

          try  :
                 if raw_msg != None : self.consumer.ack(raw_msg)

                 raw_msg = self.consumer.consume(self.queue.qname)
                 if raw_msg == None : continue

                 # make use it as a dd_message

                 self.msg.from_amqplib(raw_msg)

                 self.logger.info("Received topic   %s" % self.msg.topic)
                 self.logger.info("Received notice  %s" % self.msg.notice)
                 self.logger.info("Received headers %s\n" % self.msg.hdrstr)

                 # check for  from_cluster and source in headers

                 if not 'from_cluster' in self.msg.headers :
                    self.logger.info("skipped : no from_cluster in message headers")
                    continue

                 # skip if from_cluster is not self.broker.hostname

                 if self.msg.headers['from_cluster'] == self.from_cluster :
                    self.logger.info("on current cluster %s\n" % self.from_cluster )
                    continue

                 # ok ship log to appropriate log_cluster

                 if self.cluster != self.msg.headers['from_cluster']:
                    self.logger.info("not processing cluster %s in this process\n" % self.from_cluster )
                    continue

                 ok = self.pub.publish( self.exchange, self.msg.topic, self.msg.notice, self.msg.headers )
                 if ok : self.logger.info("published to %s %s" % (self.broker.geturl(),self.exchange))

          except :
                 (type, value, tb) = sys.exc_info()
                 self.logger.error("Type: %s, Value: %s,  ..." % (type, value))

    def reload(self):
        self.logger.info("dd_log2clusters reload")
        self.close()
        self.index = self.instance - 1
        self.configure()
        self.run()

    def start(self):
        self.logger.info("dd_log2clusters start")
        self.index = self.instance - 1
        self.configure()
        self.run()

    def stop(self):
        self.logger.info("dd_log2clusters stop")
        self.close()
        os._exit(0)
                 

# ===================================
# MAIN
# ===================================

def main():

    action = None
    args   = None
    config = None

    if len(sys.argv) >= 3 :
       action = sys.argv[-1]
       if len(sys.argv) > 3: args = sys.argv[1:-1]

    log2clusters = dd_log2clusters(config,args)

    if   action == 'reload' : log2clusters.reload_parent()
    elif action == 'restart': log2clusters.restart_parent()
    elif action == 'start'  : log2clusters.start_parent()
    elif action == 'stop'   : log2clusters.stop_parent()
    elif action == 'status' : log2clusters.status_parent()
    else :
           log2clusters.logger.error("action unknown %s" % action)
           sys.exit(1)

    sys.exit(0)



# =========================================
# direct invocation
# =========================================

if __name__=="__main__":
   main()