#! /usr/bin/python

# update: March 4, 2021 - separating ffmpeg args and ffmpeg command
# update: February 23, 2021 - using re for extracting numbers from string
# update: February 23, 2021 - multithreading to communicate between gtk and pexpect (ffmpeg and ffprobe)
# update: February 17, 2021 - updated to work with pexpect instead of subprocess - apt-get install python-pexpect
# update: November 15, 2020 - updated to work with Gtk 3.0 - updated to work with ffmpeg only
# update: October 26, 2019 - updated to work with for avidemux 2.7


# import json

import re

import thread

import pexpect
# import subprocess

import os
import datetime
import sys
import math

import gi
# import pygtk
# import gtk
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

########################################################################
# BaseClass ############################################################
########################################################################
class BaseClass(object):
	def __setattr__(self, key, value):
		if hasattr(self, key):
			self.__dict__[key] = value
		else:
			# raise AttributeError(f"\"{key}\" is not defined in \"{self.__class__.__name__}\"")
			raise AttributeError("You are using an undefined class member!")

########################################################################
# JobClass #############################################################
########################################################################
class JobClass(BaseClass):
	
	
	__fn_in = "" 
	__fn_out = ""
	__ffmpeg_args = ""
	__ext_out = ""
	
	__tvm_iter = None
	
	# __conversion_cmd = ""
	__length_probe_cmd = ""
	__resolution_probe_cmd = ""
	__status = 0
	__progress = -1.0

	
	
	def __init__(self, fn_in, ext_out, ffmpeg_args): #ccmd, lpcmd):
		# self.__conversion_cmd = ccmd
		# self.__length_probe_cmd = lpcmd
		self.__fn_in = fn_in
		self.__ext_out = ext_out
		self.__fn_out = fn_in + "." + ext_out
		self.__ffmpeg_args = ffmpeg_args
		
					
		# self.__length_probe_cmd = ("ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of default=nokey=1:noprint_wrappers=1" +
					# " \"" + fn_in + "\"")		
		self.__length_probe_cmd = ("ffmpeg -i \"" + fn_in + "\" -map 0:v:0 -c copy -f null -") # Faster than ffprobe! (see below)		
		
		self.__resolution_probe_cmd = ("ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of default=noprint_wrappers=1 \"" + fn_in + "\"")
		
		print self.__resolution_probe_cmd
	def setTreeViewModelIter(self, tvm_iter):
		self.__tvm_iter = tvm_iter
		
	def getTreeViewModelIter(self):
		return self.__tvm_iter
				
	def getInputFilename(self):
		return self.__fn_in
		
	def getOutputFilename(self):
		return self.__fn_out
		
	def setStatus(self, sts):
		self.__status = sts
		
	def setProgress(self, prg):
		self.__progress = prg		
		
	def getStatus(self):
		return self.__status
		
	def getStatusText(self):
		ret = ""
		if (self.__status == 0): # Not started
			ret = "-"
		elif (self.__status == 1): # Probing
			ret = "Preparing..."
		elif (self.__status == 2): # Converting
			tmp = '%.2f' % self.__progress
			ret = "Converting..." + tmp + "%"
		elif (self.__status == 3): # Finished
			ret = "Finished!"
		elif (self.__status == 4): # Error
			ret = "Error!"
		return ret
		
	def getProgress(self):
		return self.__progress
		
	# def getConversionCommand(self):
		# return self.__conversion_cmd
		
	def getFFMPEGArgs(self):
		return self.__ffmpeg_args
		
	def getLengthProbeCommand(self):
		return self.__length_probe_cmd		
		
	def getResolutionProbeCommand(self):
		return self.__resolution_probe_cmd		
	
########################################################################
# FFMPEGClass ##########################################################
########################################################################
class FFMPEGClass(BaseClass):
	
	__job_list = []
	__gui = []
	
	def __init__(self):
		pass
		
	def connectGui(self, gui):
		self.__gui = gui
		
	def clearJobs(self):
		self.__job_list.clear()
		self.__tree_view_model.clear()
		
	def addJobs(self, filenames):
		tvm = self.__gui.getTreeViewModel()
		
		for fn in filenames:
			
			ext_out = "avi"
			ffmpeg_args = (" -c:v mpeg4 " +  # # "-c:v", "libx264",
					       " -tag:v DIVX " +
					       " -crf 15 " +
					       " -q:v 2 ") 					
			
			new_job = JobClass(fn, ext_out, ffmpeg_args)
			fn_out = new_job.getOutputFilename()
			
			self.__job_list.append(new_job)
			tvm_iter = tvm.append([fn, fn_out, "---"])
			new_job.setTreeViewModelIter(tvm_iter)


	def runJobs(self):    
		thread.start_new_thread(self.__runJobs__, ())

	def __runJobs__(self):
		for job in self.__job_list:
			print job.getInputFilename()
			
			length_probe_cmd = job.getLengthProbeCommand()
			resolution_probe_cmd = job.getResolutionProbeCommand()
			# conversion_cmd = job.getConversionCommand()
			ffmpeg_args = job.getFFMPEGArgs()
			
			job.setStatus(1) # probing stared
			self.__gui.refreshJobList(job)
			
			# # # Probing - Frame count
			thread = pexpect.spawn(length_probe_cmd)
			cpl = thread.compile_pattern_list([
				pexpect.EOF,
				# "\d+"
				"frame= *\d+"
				# '(.+)'
			])
			while True: #TODO: stop button in gui?
				i = thread.expect_list(cpl, timeout=None)
				if i == 0: # EOF
					# print "the sub process exited 1"
					break
				elif i == 1:
					tmp = thread.match.group(0)
					tmp = [int(s) for s in re.findall(r'-?\d+\.?\d*', tmp)]
					frame_number = int(tmp[0])
					print "FRAME COUNT: " + str(frame_number)
					thread.close # or just "break"?
				elif i == 2:
					#unknown_line = thread.match.group(0)
					#print unknown_line
					pass
			thread.close()	
			
			# # # Probing - Resolution count
			thread = pexpect.spawn(resolution_probe_cmd)
			cpl = thread.compile_pattern_list([
				pexpect.EOF,
				# "\s\d+"
				"width= *\d+",
				"height= *\d+"
				# '(.+)'
			])
			while True: #TODO: stop button in gui?
				i = thread.expect_list(cpl, timeout=None)
				if i == 0: # EOF
					# print "the sub process exited 2"
					break
				elif i == 1:
					tmp = thread.match.group(0)
					tmp = [int(s) for s in re.findall(r'-?\d+\.?\d*', tmp)]
					width = int(tmp[0])
					print "WIDTH: " + str(width)					
					thread.close # or just "break"?		
				elif i == 2:
					tmp = thread.match.group(0)
					tmp = [int(s) for s in re.findall(r'-?\d+\.?\d*', tmp)]
					height = int(tmp[0])
					print "HEIGHT: " + str(height)
					thread.close # or just "break"?							
				elif i == 3:
					unknown_line = thread.match.group(0)
					print unknown_line
					pass
			thread.close()				
			
			orig_width = width
			orig_height = height
			while (not((width % 4) == 0)):
				width = width-1
				
			while (not((height % 4) == 0)):
				height = height-1			
				
			# print "ORIG WIDTH: " + str(orig_width)
			# print "ORIG HEIGHT: " + str(orig_height)
			# print "WIDTH: " + str(width)
			# print "HEIGHT: " + str(height)
			
			#TODO: HERE
			if ((not(orig_width==width)) or (not(orig_height==height))):
				ffmpeg_args = (ffmpeg_args + " -vf scale=" + str(width) + ":" + str(height))
			
			conversion_cmd = ("ffmpeg " + 
							  " -y " + 
							  " -i \"" + job.getInputFilename() + "\"" + 
							  " " + ffmpeg_args + " "  +
							  " \"" + job.getOutputFilename() + "\"")		
			

			print conversion_cmd
			job.setStatus(2) # conversion stared
			job.setProgress(0) 
			self.__gui.refreshJobList(job)			
			
			# # # Conversion
			thread = pexpect.spawn(conversion_cmd)
			cpl = thread.compile_pattern_list([
				pexpect.EOF,
				"frame= *\d+"
				# '(.+)'
				# "^(frame=.*)"
			])
			while True: #TODO: stop button in gui?
				i = thread.expect_list(cpl, timeout=None)
				if i == 0: # EOF
					print "the sub process exited 3"
					break
				elif i == 1:
					tmp = thread.match.group(0)
					# print tmp
					tmp = [int(s) for s in re.findall(r'-?\d+\.?\d*', tmp)]
					current_frame_number = int(tmp[0])
					tmp = 100.0*float(current_frame_number)/float(frame_number)
					job.setProgress(tmp)
					self.__gui.refreshJobList(job)
					thread.close # or just "break"?
				elif i == 2:
					#unknown_line = thread.match.group(0)
					#print unknown_line
					pass
					
			job.setStatus(3) # conversion ended
			self.__gui.refreshJobList(job)		
								
			thread.close()	
			print "CLOS"
	
		
########################################################################
# GuiClass #############################################################
########################################################################
class GuiClass(BaseClass):
	
	__main_win = None
	__tree_view_model = None
	__tree_view = None
	
	__ffmpeg = None
	
	def __init__(self):
		
		## Create window
		self.__main_win = Gtk.Window()
		self.__main_win.set_size_request(640, 480)
		self.__main_win.connect("destroy", Gtk.main_quit)
		#win.connect("show", on_window_show, dialog)
		
		# |->| Outer vbox
		outer_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL) 
		self.__main_win.add(outer_vbox)
		
		# Toolbar
		toolbar = Gtk.Toolbar();
		
		# load_tool_button = Gtk.ToolButton(label="Load")
		load_tool_button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_OPEN)
		signal = load_tool_button.connect('clicked', self.__onLoadToolButtonClicked, None)
		
		execute_tool_button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_EXECUTE)
		signal = execute_tool_button.connect('clicked', self.__onExecuteToolButtonClicked, None)
		
		toolbar.insert(load_tool_button, 0)
		toolbar.insert(execute_tool_button, 1)
		
		outer_vbox.add(toolbar)
		
		#### Treeview model
		self.__tree_view_model = Gtk.ListStore(str, str, str)		

		#### Treeview
		self.__tree_view = Gtk.TreeView(self.__tree_view_model)
		
		cell = Gtk.CellRendererText()
		col = Gtk.TreeViewColumn("File names", cell, text=0)
		self.__tree_view.append_column(col)
		
		cell = Gtk.CellRendererText()
		col = Gtk.TreeViewColumn("New file names", cell, text=1)
		self.__tree_view.append_column(col)	
			
		cell = Gtk.CellRendererText()
		col = Gtk.TreeViewColumn("Status", cell, text=2)
		self.__tree_view.append_column(col)	
			
		# # TODO TEMPORARY, REMOVE THIS LATER?
		# cell = Gtk.CellRendererText()
		# col = Gtk.TreeViewColumn("Abs pos", cell, text=2)
		# treeview.append_column(col)		
		
		# treeview.get_selection().connect("changed", self.on_treeview_changed)
		
		outer_vbox.add(self.__tree_view)

	def show(self):	
		self.__main_win.show_all()
		Gtk.main()
		
	def getTreeViewModel(self):
		return self.__tree_view_model

	def connectFFMPEG(self, ffmpeg):
		self.__ffmpeg = ffmpeg
		
	def refreshJobList(self, job):
		job_iter = job.getTreeViewModelIter()
		status = job.getStatusText()
		self.__tree_view_model[job_iter][2] = status
		
	def __onExecuteToolButtonClicked(self, widget, data):
		self.__ffmpeg.runJobs()
		
		
	def __onLoadToolButtonClicked(self, widget, data):

		load_dialog = Gtk.FileChooserDialog("Load files",
									   None,
									   Gtk.FileChooserAction.OPEN)
									   # (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
										# Gtk.STOCK_OPEN, Gtk.RESPONSE_OK))
										
		load_dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
										
		# dialog.set_default_response(Gtk.RESPONSE_OK)
		load_dialog.set_select_multiple(1)
		
		load_dialog.connect("response", self.__onLoadDialogResponse, None)
		
		#filter = gtk.FileFilter()
		#filter.set_name("All files")
		#filter.add_pattern("*")
		#dialog.add_filter(filter)

		#filter = gtk.FileFilter()
		#filter.set_name("Images")
		#filter.add_mime_type("image/png")
		#filter.add_mime_type("image/jpeg")
		#filter.add_mime_type("image/gif")
		#filter.add_pattern("*.png")
		#filter.add_pattern("*.jpg")
		#filter.add_pattern("*.gif")
		#filter.add_pattern("*.tif")
		#filter.add_pattern("*.xpm")
		#dialog.add_filter(filter)
		#dialog.set_size_request(350, 200)

		load_dialog.run()

	def __onLoadDialogResponse(self, dialog, response_id, data):
		
		if (response_id==Gtk.ResponseType.CANCEL):
			dialog.close()
			# TODO: CLOSE APP!
			pass
			
		elif (response_id==Gtk.ResponseType.OK):
			
			filenames = dialog.get_filenames()
			
			dialog.destroy()
			dialog.close()
			nFilenames = len(filenames)
			
			if (nFilenames > 0):
				self.__ffmpeg.addJobs(filenames)
				
			


def main():

	gui = GuiClass()
	ffmpeg = FFMPEGClass()
	gui.connectFFMPEG(ffmpeg)
	ffmpeg.connectGui(gui)

	gui.show()

	return 0

				
	


if __name__ == "__main__":
    main()
