#!/usr/bin/env python3
import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import os.path
import runpy
import subprocess
#from Cocoa import *


def getConfigPath():
	home = os.path.expanduser("~")
	return os.path.join(home, ".config/traythingy.cfg.py")


def load_file_watch(parent, filename, callback):
	def cb(p=""):
		try:
			with open(filename, "r") as f:
				data = f.read()
		except:
			return
		callback(data)
	fsw = QtCore.QFileSystemWatcher([filename], parent)
	fsw.fileChanged.connect(cb)
	cb()

class OutWnd(QtWidgets.QWidget):
	def __init__(self, item, parent=None):
		super().__init__(parent)
		self.config = item
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.setWindowTitle(item.get("showTitle", "Output"))
		self.initUI()
		self.resize(500,200)
		self.show()
		self.activateWindow()
		self.txt.setStyleSheet("background-color: #ffeeaa")
		self.txt.setText(item["exec"] + "\n")
		self.proc = QtCore.QProcess()
		self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
		self.proc.readyReadStandardOutput.connect(
			lambda: self.txt.append(str(self.proc.readAllStandardOutput().data().decode('utf-8'))))
		self.proc.finished.connect(self.procFinished)
		self.proc.start(item["exec"])
	def procFinished(self, code, status):
		self.txt.append("\nProcess exited with code "+str(code)+", status "+str(status)+"\n")
		if code == 0:
			self.txt.setStyleSheet("background-color: #aaffaa")
		else:
			self.txt.setStyleSheet("background-color: #ffaaaa")
		if not self.config.get("keep",False):
			QtCore.QTimer.singleShot(250, lambda: self.close())

	def initUI(self):
		self.setLayout(QtWidgets.QVBoxLayout())
		self.layout().setContentsMargins(QtCore.QMargins(0,0,0,0))
		self.txt = QtWidgets.QTextEdit()
		self.layout().addWidget(self.txt)
	def keyPressEvent(self, evt):
		print("key",evt,evt.key())
		if evt.key() == QtCore.Qt.Key_Control:
			self.config['keep']=True
		if evt.key() == QtCore.Qt.Key_Escape:
			if self.proc.state() == QtCore.QProcess.Running:
				self.proc.kill()
			else:
				self.close()


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
	def initMenu(self, configCode):
		self.menu = QtWidgets.QMenu(self.parent())
		self.menuItems = []
		
		self.confModule = exec(configCode, {'app':self})
		
		exitAction = self.menu.addAction("Exit")
		exitAction.triggered.connect(self.exit)
		
		self.setContextMenu(self.menu)
	
	def addItem(self, **item):
		self.menuItems.append(item)
		action = self.menu.addAction(item['name'])
		if 'icon' in item:
			action.setIcon(QtGui.QIcon(item['icon']))
		if 'exec' in item or 'func' in item:
			action.triggered.connect(lambda c,idx=len(self.menuItems)-1: self.doAction(idx))
		else:
			action.setDisabled(True)
	def addSeparator(self):
		self.menu.addSeparator()
	def addTitle(self, text):
		self.menu.addSection(text)
	def doAction(self, idx):
		item = self.menuItems[idx]
		print("running",idx,item)
		if 'exec' in item:
			try:
				self.wnd = OutWnd(item)
				#self.wnd.raise()
				#NSApp.activateIgnoringOtherApps_(True)
				#QtWidgets.QMessageBox.information(self.parent(), "Output", out.decode("utf-8", "replace"))

			except Exception as e:
				print(e)
				QtWidgets.QMessageBox.warning(self.parent(), "Error", str(e))
		elif 'func' in item:
			item['func'](self)

	def __init__(self, icon, parent=None):
		super().__init__(icon, parent)
		load_file_watch(self, getConfigPath(), self.initMenu)
	
	def exit(self):
		QtCore.QCoreApplication.exit()







class SimplePythonEditor(QsciScintilla):
	ARROW_MARKER_NUM = 8

	def __init__(self, parent=None):
		super().__init__(parent)

		# Set the default font
		#font = QFont()
		#font.setFamilies(['Monaco', 'Courier New'])
		#font.setFixedPitch(True)
		#font.setPointSize(11)
		#self.setFont(font)
		#self.setMarginsFont(font)

		# Margin 0 is used for line numbers
		#fontmetrics = QFontMetrics(font)
		#self.setMarginsFont(font)
		#self.setMarginWidth(0, fontmetrics.width("00000") + 6)
		self.setMarginWidth(0, 45)
		self.setMarginLineNumbers(0, True)
		self.setMarginsBackgroundColor(QColor("#cccccc"))

		# Clickable margin 1 for showing markers
		self.setMarginSensitivity(1, True)
		self.marginClicked.connect(self.on_margin_clicked)
		self.selectionChanged.connect(self.on_selection_changed)
		self.cursorPositionChanged.connect(self.on_cursor_position_changed)
		self.markerDefine(QsciScintilla.RightArrow,
			self.ARROW_MARKER_NUM)
		self.setMarkerBackgroundColor(QColor("#ee1111"),
			self.ARROW_MARKER_NUM)

		# Brace matching: enable for a brace immediately before or after
		# the current position
		#
		self.setBraceMatching(QsciScintilla.SloppyBraceMatch)

		# Current line visible with special background color
		self.setCaretLineVisible(True)
		self.setCaretLineBackgroundColor(QColor("#ffe4e4"))

		# Set Python lexer
		# Set style for Python comments (style number 1) to a fixed-width
		# courier.
		#

		#lexer = QsciLexerPython()
		lexer = QsciLexerFormatinfo()
		#lexer.setDefaultFont(font)
		self.setLexer(lexer)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, QsciScintilla.STYLE_DEFAULT, b'Courier New')
		self.SendScintilla(QsciScintilla.SCI_STYLESETSIZE, QsciScintilla.STYLE_DEFAULT, 11)
		self.SendScintilla(QsciScintilla.SCI_STYLECLEARALL)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciLexerCPP.CommentLine, 0x777777)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciLexerCPP.Comment, 0x666666)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciLexerCPP.Keyword, 0x0000aa)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciLexerCPP.KeywordSet2, 0x000055)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciLexerCPP.SingleQuotedString, 0x00aa00)
		self.SendScintilla(QsciScintilla.SCI_STYLESETFORE, QsciLexerCPP.DoubleQuotedString, 0x00aa00)

		# Don't want to see the horizontal scrollbar at all
		# Use raw message to Scintilla here (all messages are documented
		# here: http://www.scintilla.org/ScintillaDoc.html)
		self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

		# not too small
		self.setMinimumSize(600, 450)

	def on_margin_clicked(self, nmargin, nline, modifiers):
		# Toggle marker for the line the margin was clicked on
		if self.markersAtLine(nline) != 0:
			self.markerDelete(nline, self.ARROW_MARKER_NUM)
		else:
			self.markerAdd(nline, self.ARROW_MARKER_NUM)

	def on_selection_changed(self):
		pass

	def on_cursor_position_changed(self, a, b):
		try:
			pos = self.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)
			print(a,b,pos)
			style = self.SendScintilla(QsciScintilla.SCI_GETSTYLEAT, pos)
			print(a,b,pos,style)
		except Exception as e:
			print(e)


def showScintillaDialog(parent, title, content, ok_callback):
	dlg = QDialog(parent)
	dlg.setWindowTitle(title)
	dlg.setLayout(QVBoxLayout())
	sg = SimplePythonEditor()
	sg.setText(content)
	dlg.layout().addWidget(sg)
	makeDlgButtonBox(dlg, ok_callback, lambda: sg.text())
	if dlg.exec() == QDialog.Rejected: return None
	return sg.text()







def main(image):
	app = QtWidgets.QApplication(sys.argv)
	app.setQuitOnLastWindowClosed(False)
	w = QtWidgets.QWidget()
	trayIcon = SystemTrayIcon(QtGui.QIcon(image), w)
	trayIcon.show()
	sys.exit(app.exec_())


if __name__ == '__main__':
	on='rainbow_1f308.png'
	main(on)
