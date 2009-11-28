from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.application import internet, service

from twisted.mail.smtp import ESMTPSenderFactory
from email.MIMEText import MIMEText

import re, StringIO, time, os


class Watcher(DatagramProtocol):
    
        """
        Whenever a new entry is added to doord's log file, the Watcher 
        class checks the new line against a whitelist of messages that 
        are safe to ignore, listed as in self.regexes. 
        If the content of the entry doesn't match these regexes, and is
        considered to represent an error state, the Watcher will send
        an email to admin staff
        """
      
	receipients = []
	template_texts = {
		'transition_to_log_state': ["[doord] Error has been fixed", "Last line:\n%(line)s\n\nRemainder of log:\n%(log)s"],
		'transition_to_error_state': ["[doord] An error has occured", "Offending log message:\n%s"],
		'transition_to_dead_state': ["[doord] Missed Hearbeat", "The monitored instances has not been heard from for %d seconds"],
		'recurrent_in_error_state': ["[doord] An error is persistent", "log messages:\n%s"]
	}
  # These regexes are are checked against to see if a message counts as an error or not.
  # We're assumign anything that doesn't fit these is bad.
	regexes = [
		"\[-\] ReportedHealthCheck no errors",
		"\[-\] Pipeline .* opening door for authentication result success",
		"\[-\] PerleActuator operated while in activation cycle",
		"\[HTTPChannel,.*\] .*"
	]

	log_file = "/var/log/doord.log"

	smtp_sender = "doord@domain.tld"
	smtp_user = ""
	smtp_password = ""
	smtp_host = ""
	smtp_port = 25

	twitter_user = ""
	twitter_password = ""

	minimum_interval = 2
	maximum_interval = 20
	heart_beat_interval = 120
	log = []

	in_error_state = False
	last_read = 0

	def __init__(self):
		"""setup the Watcher class, and initialize the heartbeat monitor"""
		self.heartbeat_check()

	def datagramReceived(self, data, (host, port)):
		self.process_line(data[4:])

	def process_line(self, line):
		"""process a single log entry"""
		self.last_read = time.time()
		print line
		# we want to log everything from the box
		self.queue_error_log(line)

		# but have the notification only action on doord mesags
		if not "doord" in line:
			return False

		if self.error(line[16:]) and not self.in_error_state:
			print "have error %s" % line
			self.transition_to_error_state(line)
		elif not self.error(line[16:]) and self.in_error_state:
			print "end error"
			self.transition_to_log_state(line)

	def queue_error_log(self, line):
	    """this appends the latest log message sent from the door monitor to the logfile"""
		output = file(self.log_file, "a")
		output.write(line + "\n")
		output.close()

	# hearbeat monitor
	def heartbeat_check(self):
		"""
		This is called every minute to see if the monitored doord instance is still alive. 
		If all is well, we simply set another heartbeat_check to be called in one minute.
		If something is wrong, we switch to being in an error state.
		"""
		print "heartbeat_check"
		if not self.in_error_state and self.last_read != 0 and time.time() - self.last_read > self.heart_beat_interval:
			print "missed heartbeat"
			self.transition_to_dead_state()
		reactor.callLater(60, self.heartbeat_check)

	# state logic
	def error(self, line):
		"""eval whether a given line is a log entry representing an error state"""
		for regex in self.regexes:
			if re.match(regex, line):
				return False
		return True

	def transition_to_dead_state(self):
		self.notify_admins_with('transition_to_dead_state', time.time() - self.last_read)
		self.in_error_state = True

	def transition_to_error_state(self, line):
		self.notify_admins_with('transition_to_error_state', line)
		self.in_error_state = True
		#self.timer.callback(self.minimum_interval){send_log_to_admins(self.minimum_interval)}

	def transition_to_log_state(self, line):
		self.notify_admins_with('transition_to_log_state', {'line': line, 'log': self.log})
		self.in_error_state = False


	# notification logic
	def notify_admins_with(self, notification_type, args):
		template_text = self.template_texts[notification_type]
		for receipient in self.receipients:
			self.send_email_to(template_text, args, receipient)

		if self.twitter_notification_enabled();
			self.send_twitter_notification(template_text, args)

	# email logic
	def send_email_to(self, template, args, receipient):
		msg = MIMEText(template[1] % args)
		msg["Subject"] = template[0]
		msg["From"] = "doord"
		msg["To"] = receipient

		resultDeferred = Deferred()

		senderFactory = ESMTPSenderFactory(
			self.smtp_user,
			self.smtp_password,
			self.smtp_sender,
			receipient,
			StringIO.StringIO(msg.as_string()),
			resultDeferred)

		reactor.connectTCP(self.smtp_host, self.smtp_port, senderFactory)

		return resultDeferred

	def send_log_to_admins(self, time_since_last_call):
		notify_admins_with('recurrent_in_error_state', self.log)
		self.log = []
		#time_to_next_call = if time_since_last_call == self.maximum_interval:
		#						self.maximum_interval
		#					else:
		#						time_since_last_call * 2
		#self.timer.callback(time_to_next_call){send_log_to_admins(time_to_next_call)}

	# twitter logic
	def twitter_notification_enabled(self):
		return self.twitter_user != ""

	def send_twitter_notification(self, template, args):
		# append the subject with the content and limit it to 140 chars
		update = (template[0] + (template[1] % args))[:140]
		command = "curl --basic --user %s:%s --data status=\"%s\" http://twitter.com/statuses/update.xml" % (self.twitter_user, self.twitter_password, update)
		os.popen(command)

application = service.Application('doord')
serviceCollection = service.IServiceCollection(application)
internet.UDPServer(514, Watcher()).setServiceParent(serviceCollection)


