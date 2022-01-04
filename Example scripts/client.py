#!/usr/bin/python

import socket

image_address = ('127.0.0.1', 52986)
control_address = ('127.0.0.1', 52985)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto("Hello world", control_address)

data = sock.recv(2048)
print ":".join("{:02x}".format(ord(c)) for c in data)

