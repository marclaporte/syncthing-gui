#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonProcess

Runs syncthing daemon process as subprocess of application
"""

from __future__ import unicode_literals
from gi.repository import Gio, GLib, GObject
from syncthing_gtk import DEBUG
from collections import deque
import os, sys

class DaemonProcess(GObject.GObject):
	__gsignals__ = {
		# line(text)	- emited when process outputs full line
		b"line"			: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
		# exit(code)	- emited when process exits
		b"exit"			: (GObject.SIGNAL_RUN_FIRST, None, (int,)),
	}
	SCROLLBACK_SIZE = 500	# Maximum number of output lines stored in memory
	
	def __init__(self, commandline):
		""" commandline should be list of arguments """
		GObject.GObject.__init__(self)
		flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
		self._cancel = Gio.Cancellable()
		os.environ["STNORESTART"] = "1"	# see syncthing --help
		self._proc = Gio.Subprocess.new(commandline, flags)
		self._proc.wait_check_async(None, self._cb_finished)
		self._lines = deque([], DaemonProcess.SCROLLBACK_SIZE)
		self._buffer = ""
		self._stdout = self._proc.get_stdout_pipe()
		self._stdout.read_bytes_async(256, 0, self._cancel, self._cb_read)
	
	def _cb_read(self, proc, results):
		response = proc.read_bytes_finish(results)
		response = response.get_data().decode('utf-8')
		self._buffer = "%s%s" % (self._buffer, response)
		while "\n" in self._buffer:
			line, self._buffer = self._buffer.split("\n", 1)
			self._lines.append(line)
			self.emit('line', line)
		if not self._cancel.is_cancelled():
			GLib.idle_add(self._stdout.read_bytes_async, 256, 1, None, self._cb_read)
	
	def _cb_finished(self, proc, results):
		try:
			r = proc.wait_check_finish(results)
			print "Subprocess finished", proc.get_exit_status()
		except GLib.GError:
			# Exited with exit code
			print "Subprocess exited", proc.get_exit_status()
		self.emit('exit', proc.get_exit_status())
		self._cancel.cancel()
	
	def terminate(self):
		""" Terminates process (sends SIGTERM) """
		self._proc.send_signal(15)
	
	def kill(self):
		""" Kills process (sends SIGTERM) """
		self._proc.force_exit()
	
	def get_output(self):
		""" Returns process output as iterable list of lines """
		return self._lines
