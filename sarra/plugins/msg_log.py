#!/usr/bin/python3

"""
  the default on_msg handler for sr_log.
  prints a simple notice.

"""

class Msg_Log(object): 

    def __init__(self,parent):
        parent.logger.info("msg_log initialized")
          
    def perform(self,parent):
        msg = parent.msg
        parent.logger.info("msg_log received: %s %s%s topic=%s lag=%g %s" % \
           tuple( msg.notice.split()[0:3] + [ msg.topic, msg.get_elapse(), msg.hdrstr ] ) )
        return True

msg_log = Msg_Log(self)

self.on_message = msg_log.perform

