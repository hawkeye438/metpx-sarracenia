
Status: Pre-Draft

----------------------------
Thinking about post messages
----------------------------

Text here is just notes, not settled, looking at different considerations, constraints, requirements.
Many different angles discussed here.  Conclusions graduate to sr_post.1 man page which contains
only net result of discussions.


v01.post: Is there post AND notify?
-----------------------------------

post was supposed to be the same thing as notify.  Michel said they are different, do not know why.
We talked, and I think it has been captured in the different ways of interpreting srcpath and 
relpath in messages.txt there was never any intent to have two different messages (post and notify) 
need to understand whether that is truly needed, and why.

There should be only one type, but maybe it is clearer to have two?  


v01.post: flag syntax 
---------------------

how to represent flags in post messages.  There are flags with arguments and without.

For illustration assume the following flags:

	o - a boolean flag
	k - a flag that has 'karg' as a value.
	j - a flag that has 'jarg' as a value.

Look at different ways of representing those flags:

 - prefer a single space-separated field within a sr.post message for unix filter command compatibility.
   post syntax is re-used by log messages 
   (logs are just post messages with a suffix, and a different topic)
 - Assume default value is false when k omitted, true when present.
 - cannot have spaces or other things that need to be URL encoded %20% ?
   aim is to ensure that all flags fit as a single field in a space separated line.
 - assume that one letter flags is all we need.  
 - Since this will show up in every post, and posts are very common, there is some interest in
   minimizing the size of them in bytes.
 - do we need nesting?  (flags with lists as values?) give a +mark for ones that do support that.
 - get a net score for options by adding all the +&-s to get a net number.

Syntax options so far:

flags followed by args:     
	okj-karg,jarg

::

        + least bytes. This will show up very often.
        - hard to parse for computers and people, need to associate left & right.
        net: 0
	
comma separated keyword=value pairs:
	o,k=karg,j=jarg

	++ very easy to parse and understand.
	+ extensible for flags >1 letter.
	net: +3

json:
	{"o":true,"k":"karg","j":"jarg"}
	+ use a standard parser module.
	-- more characters
	-- harder to read without a parser (grep/awk)
	+ extensible for flags >1 letter.
	+ supports nesting, can use brackets, etc...
	net: -1

AMQP headers:
	++ easy (no parsing)
	+ supports nesting, can use brackets, etc...
	+ extensible for flags >1 letter.
	+ most elegant possibility of use of header based exchanges.
	+ not visible to grep/awk etc... unless we do something on print.
	net: +1


v01.post: how to specify scope 
------------------------------

how to specify ´scope´ is still unsettled.

use a flag with a list?
	s=ddi-ddbeta-

repeat the same flag?
	s=ddi,s=ddbeta,s= ...

add a separate element to the post message
	<scope> = comma separated list of destinations.

Things to think about:
	- the post goes to all clients...
	- do we want all recipients knowing which scopes a message targets?

information about a scope might not be something to share with all consumers.
Putting it ´out of band´ makes some sense.  an AMQP header might make sense
to avoid modifying the message as it traverses switches, and making scope
information too easily available.

methods of addressing scope visibility:

	- Edit the scope field as we go? (deleting irrelevant scopes?)

	- always delete scope field when posting to xPublic?
	  (meaning have arrived at a ´destination´ scope?)

	- have a setting to delete scope under admin control at a specific
	  point?

Routing between scopes is always going to be under administrator control.
the inter-switch transfer will always be something the admins of the various
switches configure and need to be aware of.

if we post on xPublic on ddsr, and ddi is subscribed to it, then...
that´s fine.

Syntax options so far:


include in flags:
	s=internal,s=public
	+- need to be able to specify multiple ones, so it is either nested, or repeated.
	+- building a csv list from a series of repeated keywords mixed in with other flags?
	-- nested syntax of some kind
	- excess characters, since always present.


add a csv field for scopes:
	It will be present on every post...

	internal,public

		o set default switch-wide.
		o 'default' when specified by client uses switch default.
		o perhaps set up abbrevs to reduce bytes:: 

                        gov - intragov (ddi)
                        nrc - nrc (does not get to sci)
                        ec  - ec (does not get to sci)
                        hpc - hpc zone (ddsr? sftp.sci...)
                        pub - public/outside of gov.

		   nobody targets ddsr in this scheme, but likely ddsr is
		   'between' nrc and pub, gov, and hpc scopes.
		   not sure if anyone actually targets hpc scope.

	+  less characters than in flags

	+- tells everyone about all destination scopes good/bad ?
	   I think it is vague enough not to be a security issue.
	   also, when posting at end switch, could just remove
	   field, replace by '-' minimizing security issues.

	   or could replace by single scope once routed to scope.

	++  easy parsing, for client programs and log parsers.

have the csv mention users instead of scopes:
	+- same as above
	-- tells everyone who else is getting stuff.
	+  gets rid of user visibility of 'scope' concept.

		

Thinking about log messages
---------------------------

Log message contains:

is only emitted after processing of an announcement is completed, 
to indicate a final status of processing that announcement.

topic matches announcement message except...

v01.log.<source>.<consumer>...... 

version is protocol version, should increment in sync with post.

start is as per post... just add fields after:

	<date> blksz blckcnt remainder blocknum flags baseurl relativeurl <flow> <status> <host> <client> <duration> 

	what if there are spaces in the file name?
	path should be url-encoded (so space is: %20 )

can we just space out the fields on a single line? or do we need fancier 
parsing....  one line is better, because grep etc... works, and 1 message 
per line is easier to parse.

Fields that needs to be there:

startdate <date-time> of transfer...
	- perhaps just indicate duration of transfer in seconds, rather than 
	   two dates.  saves few bytes.

Enddate <date-time> of transfer ... 

status 
	- ok or error code> ... use http ones?
		lots of good ones on wikipedia.

	- should topic include status?  v01.log.200..... (then do not need it in the body...)
	   cant subscribe only to errors? likely not useful as too 
	   many errors to subscribe to.  perhaps just 200 for success, 
           and 400 for failure?  

	   No, think it is a pain. just leave it in body.

flow 
	- application determined flow id, so the application can relate it to their processing.
        - flow is a display field, unchanged/untouched by sarracenia.

consumer 
	- talk to the data source, and determine what is a good label to 
	  share.  This is analogous to a company, or organization, and is 
	  likely not be unique to a single flow.
	- subscriber chosen significant id, so that source can understand 
          who has received it.
	- often subscriber will be on s12124.rogers.net ... not terribly 
          significant.
	- client id is essentially a display field... based unchanged to 
          source.

	- so only sources and clients need to negotiate the id´s,  we 
          just need to pass it in both directions transparently, and use 
          the identifier that they both know whenever appropriate.

is client the username used to connect to the broker and httpd instance?
	- in which case, it is no longer transparent to the switches, 
	  and we have to say something about it.
          so the client will see it, and it is a ''monitoring unit''

system each ddi/ddsr instance will be defined as an internal client, so internal vs. actual deliveries
are easily distinguished... does that mean each layer of switches has an amqp username?


Thinking about Configuration / Administration
---------------------------------------------

just a place holder.

really not baked yet. thinking is in configuration.txt

v01.cfg  

