# -*- coding: UTF-8 -*-
import gateway
import socketManagerWmo
import bulletinManagerWmo
import bulletinWmo
from socketManager import socketManagerException
from DiskReader import DiskReader
from MultiKeysStringSorter import MultiKeysStringSorter
import fet
import os.path

class senderWmo(gateway.gateway):
    __doc__ = gateway.gateway.__doc__ + \
    """
    #### CLASSE senderWmo ####

    Nom:
    senderWmo

    Paquetage:

    Statut:
    Classe concrete

    Responsabilites:
    -Lire des bulletins en format Wmo;
    -Envoyer les bulletins Wmo lus selon un ordre de priorite dans une arborescence;
    -Communiquer en respectant le protocole Wmo.

    Attributs:
    Attribut de la classe parent gateway

    Methodes:
    Methodes de la classe parent gateway

    Auteur:
    Pierre Michaud

    Date:
    Novembre 2004
    """

    def __init__(self,path,options,logger):
        """
        Nom:
        __init__

        Parametres d'entree:
        -path:  repertoire ou se trouve la configuration
        -logger:        reference a un objet log

        Parametres de sortie:
        -Aucun

        Description:
        Instancie un objet senderWmo.

        Auteur:
        Pierre Michaud

        Date:
        Novembre 2004
        """
        gateway.gateway.__init__(self,path,options,logger)
        self.establishConnection()
        self.options = options

        # Instanciation du bulletinManagerWmo selon les arguments issues du fichier
        # de configuration
        self.logger.writeLog(logger.DEBUG,"Instanciation du bulletinManagerWmo")

        self.unBulletinManagerWmo = bulletinManagerWmo.bulletinManagerWmo( \
                fet.FET_DATA + fet.FET_TX + options.client ,logger)
        self.options.remoteHost = options.host
        self.options.localPort = options.port
        self.options.timeout    = options.connect_timeout
        self.listeFichiersDejaChoisis = []
        self.reader = None

    def shutdown(self):
        __doc__ = gateway.gateway.shutdown.__doc__ + \
        """
        ### senderWmo ###
        Nom:
        shutdown

        Parametres d'entree:
        -Aucun

        Parametres de sortie:
        -Aucun

        Description:
        Termine proprement l'existence d'un senderWmo.  Les taches en cours sont terminees
        avant d'eliminer le senderWmo.

        Nom:
        Pierre Michaud

        Date:
        Novembre 2004
        """
        gateway.gateway.shutdown(self)

        resteDuBuffer, nbBullEnv = self.unSocketManagerWmo.closeProperly()

        self.write(resteDuBuffer)

        self.logger.writeLog(self.logger.INFO,"Le senderWmo est mort.  Traitement en cours reussi.")

    def establishConnection(self):
        __doc__ = gateway.gateway.establishConnection.__doc__ + \
        """
        ### senderWmo ###
        Nom:
        establishConnection

        Parametres d'entree:
        -Aucun

        Parametres de sortie:
        -Aucun

        Description:
        Initialise la connexion avec le destinataire.

        Nom:
        Pierre Michaud

        Date:
        Novembre 2004
        """

        # Instanciation du socketManagerWmo
        self.logger.writeLog(self.logger.DEBUG,"Instanciation du socketManagerWmo")

        self.unSocketManagerWmo = \
                 socketManagerWmo.socketManagerWmo(
                         self.logger,type='master', \
                         port=self.options.port,\
                         remoteHost=self.options.host,
                         timeout=self.options.connect_timeout)

    def read(self):
        __doc__ =  gateway.gateway.read.__doc__ + \
        """
        ### senderWmo ###
        Nom:
        read

        Parametres d'entree:
        -Aucun

        Parametres de sortie:
        -data: dictionnaire du contenu d'un fichier selon son chemin absolu

        Description:
        Lit les bulletins contenus dans un repertoire.  Le repertoire
        contient les bulletins de la priorite courante.

        Nom:
        Pierre Michaud

        Date:
        Novembre 2004
        Modifications: Janvier 2005
        """
        self.reader = DiskReader(
                 fet.FET_DATA + fet.FET_TX + self.options.client,
                 fet.clients[self.options.client][5],
                 True,
                 self.logger,
                 eval(fet.clients[self.options.client][4]) )
        self.reader.sort()
        return(self.reader.getFilesContent(fet.clients[self.options.client][5]))
        """
        data = []
        #lecture de la selection precedente
        liste = self.unBulletinManagerWmo.getListeNomsFichiersAbsolus()
        #si rien n'a ete envoye lors de la derniere lecture,
        #on considere le dernier envoi non vide effectue
        if len(liste)>=1:
                self.listeFichiersDejaChoisis = self.unBulletinManagerWmo.getListeNomsFichiersAbsolus()

        try:
                #determination des bulletins a lire et lecture de leur contenu brut
                data = self.unBulletinManagerWmo.readBulletinFromDisk(self.config.listeRepertoires,self.listeFichiersDejaChoisis,priorite=1)

                return data

        except Exception, e:
                self.logger.writeLog(self.logger.ERROR,"senderWmo.read(): Erreur lecture: %s",str(e.args))
                raise
         """


    def write(self,data):
        __doc__ =  gateway.gateway.write.__doc__ + \
        """
        ### senderWmo ###
        Nom:
        write

        Parametres d'entree:
        -data: dictionnaire du contenu d'un fichier selon son chemin absolu

        Parametres de sortie:
        -Aucun

        Description:
        Genere les bulletins en format WMO issus du dictionnaire data
        et les ecrit au socket approprie.

        Nom:
        Pierre Michaud

        Date:
        Decembre 2004
        Modifications: Janvier 2005
        """

        self.logger.writeLog(self.logger.INFO,"%d nouveaux bulletins sont envoyes",len(data))

        for index in range(len(data)):
                try:
                        rawBulletin = data[index]
                        unBulletinWmo = bulletinWmo.bulletinWmo(rawBulletin,self.logger,finalLineSeparator='\r\r\n')
                        succes = self.unSocketManagerWmo.sendBulletin(unBulletinWmo)
                        #si le bulletin a ete envoye correctement, le fichier est efface
                        if succes:
                                self.logger.writeLog(self.logger.INFO,"sent %s", os.path.basename(self.reader.sortedFiles[index]) )
                                self.unBulletinManagerWmo.effacerFichier(self.reader.sortedFiles[index])
                                self.logger.writeLog(self.logger.DEBUG,"senderWmo.write(..): Effacage de " + self.reader.sortedFiles[index])
                        else:
                                self.logger.writeLog(self.logger.INFO,"%s: probleme d'envoi ", os.path.basename(self.reader.sortedFiles[index]))
                except Exception, e:
                        if e==104 or e==110 or e==32 or e==107:
                                self.logger.writeLog(self.logger.ERROR,"senderWmo.write(): la connexion est rompue: %s",str(e.args))
                        else:
                                self.logger.writeLog(self.logger.ERROR,"senderWmo.write(): erreur: %s",str(e.args))
                        raise
