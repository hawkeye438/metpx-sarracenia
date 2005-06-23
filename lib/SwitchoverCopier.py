#!/usr/bin/env python
"""
#############################################################################################
# Name: SwitchoverCopier.py
#
# Author: Daniel Lemay
#
# Date: 2005-06-21
#
# Description: First here is a description of a DRBD pair:
#              
#   machine1:/apps/                          machine2:/apps/
#            /backupMachine2/                         /backupMachine1/
#
#   The first thing to know when using this program is the name of the mount point of the 
#   drbd partition. The name 'backupMachine?' is only an example.
#
#   When one member of a DRBD pair crash (machine1 for example), this program will be used
#   to copy data from machine2:/backupMachine1/ to machine2:/apps/. The data that will
#   be copied is coming from receivers and senders directories. The job of determining which
#   directories correspond to receivers and senders is done by an appropriate manager (PDS or PX).
# 
#   The files copied will be logged and these logs (one per directory, location: /apps/{px|pds}/switchover)
#   will be used to erase these files on machine1:/apps/
# 
#   Usage:
#
#   SwitchoverCopier (-s|--system) {PDS | PX} (-d|--drbd) DRBD_ROOT\n"
#
#   -s, --system: PDS or PX 
#   -d, --drbd: DRBD_ROOT is the mount point of the backup partition 
#
#   Suppose pds3-dev and pds4-dev are a drbd pair. pds3-dev crash, we are on pds4-dev:
#
#   example 1: SwitchoverCopier -s PDS -d '/apps.pds3-dev'
#   example 2: SwitchoverCopier -s PX -d '/apps.pds3-dev'
#
#############################################################################################
"""

from Logger import Logger
import os, pwd, sys, getopt

def usage():
    print "\nUsage:\n"
    print "SwitchoverCopier (-s|--system) {PDS | PX} (-d|--drbd) DRBD_ROOT\n"
    print "-s, --system: PDS or PX"
    print "-d, --drbd: DRBD_ROOT is the mount point of the backup partition\n"
    print "Suppose pds3-dev and pds4-dev are a drbd pair. pds3-dev crash, we are on pds4-dev:\n"
    print "example 1: SwitchoverCopier -s PDS -d '/apps.pds3-dev'"
    print "example 2: SwitchoverCopier -s PX -d '/apps.pds3-dev'\n"

class SwitchoverCopier:

    LOG_LEVEL = "INFO"                   # Logging level
    STANDARD_ROOT = 'test'

    if not os.getuid() ==  pwd.getpwnam('pds')[2]:
        pdsUID = pwd.getpwnam("pds")[2]
        os.setuid(pdsUID)

    def __init__(self):

        self.getOptionsParser() 
        #print SwitchoverCopier.DRBD

        if SwitchoverCopier.SYSTEM == 'PX': 
            from PXManager import PXManager
            manager = PXManager(SwitchoverCopier.DRBD + '/px/')
            LOG_NAME = manager.LOG + 'SwitchoverCopier.log'    # Log's name

        elif SwitchoverCopier.SYSTEM == 'PDS':
            from PDSManager import PDSManager
            manager = PDSManager(SwitchoverCopier.DRBD + '/pds/')
            LOG_NAME = manager.LOG + 'SwitchoverCopier.log'   # Log's name

        self.logger = Logger(LOG_NAME, SwitchoverCopier.LOG_LEVEL, "Copier")
        self.logger = self.logger.getLogger()
        manager.setLogger(self.logger)

        manager.afterInit()

        self.logger.info("Beginning program SwitchoverCopier")
        self.rxPaths =  manager.getRxPaths()
        self.txPaths =  manager.getTxPaths()
        self.logger.info("Receivers paths: " + str(self.rxPaths))
        self.logger.info("Senders paths: " + str(self.txPaths))

        self.manager = manager

    def getDestDir(self, sourceDir, replacement):
        parts = sourceDir.split('/', 2)
        parts[1] = replacement

        return '/'.join(parts)

    def copy(self):
        os.umask(0777)
        #for sourceDir in self.txPaths:
        #    self.manager.copyFiles(sourceDir, self.getDestDir(sourceDir))   

        for sourceDir in self.rxPaths:
            parts = sourceDir.split('/')
            self.manager.copyFiles(sourceDir, self.getDestDir(sourceDir, SwitchoverCopier.STANDARD_ROOT),
                                                              '/apps/px/switchover/' + '_'.join(parts[1:]) + '.log')   

        os.umask(0022)

    def getOptionsParser(self):
        
        system = False
        drbd = False
        try:
            opts, args = getopt.getopt(sys.argv[1:], 'd:s:h', ['help', 'system=', 'drbd='])
            #print opts
            #print args
        except getopt.GetoptError:
            # print help information and exit:
            usage()
            sys.exit(2)

        for option, value in opts:
            if option in ('-h', '--help'):
                usage()
                sys.exit()
            if option in ('-s', '--system'):
                system = True
                if value in ['PDS', 'PX']:
                    SwitchoverCopier.SYSTEM = value
                else:
                    usage()
                    sys.exit(2)
            if option in ('-d', '--drbd'):
                drbd = True
                SwitchoverCopier.DRBD = value    

        # We must give a system and a path
        if system is False or drbd is False:  
            usage()
            sys.exit(2)

if __name__ == '__main__':

    copier =  SwitchoverCopier()
    copier.copy()
