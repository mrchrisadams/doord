#!/usr/bin/python
import os, fcntl, time, ConfigParser
from socket import *

config = ConfigParser.ConfigParser()
config.read(('doord-button.conf', '/etc/doord-button.conf'))

pin = config.getint('doord-button', 'pin')
heartbeat = config.getint('doord-button', 'heartbeat')
host = config.get('doord-button', 'host')
port = config.getint('doord-button', 'port')

fd = os.open("/dev/gpio_proxy", os.O_RDWR)
fcntl.ioctl(fd, pin, 1) # Set pin state to 1
fcntl.ioctl(fd, 6, pin) # Set pin as input

sock = socket(AF_INET,SOCK_DGRAM)

state = 1
lastTime = time.time()
while (True):

    if heartbeat and (time.time() - lastTime) > heartbeat:
        try:
            sock.sendto("HB", (host, port))
        except Exception, detail:
            print "Error sending heartbeat: ", detail

        lastTime = time.time()

    button = fcntl.ioctl(fd, 7, pin) # Read pin state
    if (button != state):
        state = button

        if (state == 0):
            try:
                sock.sendto("OPEN", (host, port))
            except Exception, detail:
                print "Error sending button packet: ", detail

    time.sleep(0.05)
