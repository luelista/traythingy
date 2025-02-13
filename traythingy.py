#!/usr/bin/env python3.7
import sys, os, json
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot
import os.path
import runpy
import subprocess
#from Cocoa import *

from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciLexerCPP
from qasync import QEventLoop, QApplication, asyncSlot
import asyncio

from datetime import datetime

from easyrpc.connection import autoconnect_from_env
from easyrpc.rpc import RpcOp
from easyrpc.db import blobstore
from functools import wraps

def getConfigPath():
	home = os.path.expanduser("~")
	return os.path.join(home, ".config/traythingy/traythingy.json")


def load_file_watch(parent, filename, callback):
	def cb(p=""):
		print("load_file_watch: ",p, os.path.realpath(p) != os.path.realpath(filename), os.path.realpath(p), os.path.realpath(filename))
		fsw.addPath(filename)
		if os.path.realpath(p) != os.path.realpath(filename): return
		try:
			with open(filename, "r") as f:
				data = f.read()
		except Exception as e:
			print(e)
			return
		callback(data)
	fsw = QtCore.QFileSystemWatcher([filename, os.path.dirname(filename)], parent)
	fsw.fileChanged.connect(cb)
	fsw.directoryChanged.connect(cb)
	cb(filename)



## from : https://gist.github.com/medihack/7af1f98ea468aa7ad00102c7d84c65d8
def async_debounce(wait):
	def decorator(func):
		waiting = False

		@wraps(func)
		async def debounced(*args, **kwargs):
			nonlocal waiting

			def call_func():
				nonlocal waiting
				waiting = False
				asyncio.ensure_future(func(*args, **kwargs))

			if not waiting:
				asyncio.get_running_loop().call_later(wait, call_func)
				waiting = True

		return debounced

	return decorator


class OutWnd(QtWidgets.QWidget):
	def __init__(self, item, config, parent=None):
		super().__init__(parent)
		self.itemInfo = item
		self.config = config
		if "exec" in item:
			self.cmdLine = item["exec"]
			if "run_on" in item:
				if item["run_on"] != self.config['hostname']:
					self.cmdLine = self.config['remotes'][item['run_on']] + self.cmdLine
		elif "http_get" in item:
			self.cmdLine = 'curl "%s"' % item["http_get"]
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.setWindowTitle(item.get("showTitle", "Output"))
		self.initUI()
		self.resize(500,200)
		self.show()
		self.activateWindow()
		self.txt.setStyleSheet("background-color: " + ("#ffffff" if self.itemInfo.get("keep",False) else "#ffeeaa"))
		self.txt.setText(self.cmdLine + "\n")
		self.proc = QtCore.QProcess()
		self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
		self.proc.readyReadStandardOutput.connect(
			lambda: self.txt.append(str(self.proc.readAllStandardOutput().data().decode('utf-8'))))
		self.proc.finished.connect(self.procFinished)
		print("CMD:",self.cmdLine)
		self.proc.start("sh", ["-c", self.cmdLine])

	def procFinished(self, code, status):
		self.txt.append("\nProcess exited with code "+str(code)+", status "+str(status)+"\n")
		if code == 0:
			self.txt.setStyleSheet("background-color: #aaffaa")
			if not self.itemInfo.get("keep",False):
				QtCore.QTimer.singleShot(250, lambda: self.close())
		else:
			self.txt.setStyleSheet("background-color: #ffaaaa")

	def initUI(self):
		self.setLayout(QtWidgets.QVBoxLayout())
		self.layout().setContentsMargins(QtCore.QMargins(0,0,0,0))
		self.txt = QtWidgets.QTextEdit()
		self.layout().addWidget(self.txt)

	def keyPressEvent(self, evt):
		print("key",evt,evt.key())
		if evt.key() == QtCore.Qt.Key_Control:
			self.itemInfo['keep']=True
			self.txt.setStyleSheet("background-color: " + "#ffffff" )
		if evt.key() == QtCore.Qt.Key_Escape:
			if self.proc.state() == QtCore.QProcess.Running:
				self.proc.kill()
			else:
				self.close()

from easyrpc.helpers import AsyncSignal

class DocDb:
	def __init__(self, rpc):
		self.documents = {}
		self.rpc = rpc
		self.remote_item_updated = AsyncSignal()

	async def _update_doc(self, doc_id, items):
		if doc_id not in self.documents:
			self.documents[doc_id] = dict()
		for item in items:
			self.documents[doc_id][item['id']] = item
		await self.remote_item_updated.emit(doc_id, items)

	async def fetch_doc(self, doc_id):
		if doc_id in self.documents: return
		result = await self.rpc.caller.node('pb').pb.pb.get_updates([[doc_id, 0]], True)
		for doc in result['docs']:
			await self._update_doc(doc['document'], doc['items'])
	
	async def get_items(self, doc_id):
		await self.fetch_doc(doc_id)
		return self.documents[doc_id]

	async def search(self, doc_id=None, filter=None, order_by=None, order_desc=False):
		if doc_id:
			await self.fetch_doc(doc_id)
			items = self.documents[doc_id].values()
		else:
			items = (item for doc in self.documents.values() for item in doc)
		items = (item for item in items if not item.get('deleted'))
		if filter:
			items = (item for item in items if filter(item))
		if order_by:
			items = sorted(items, key=lambda item: item.get(order_by), reverse=order_desc)
		return items

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
	async def add_item(self, idx, item):
		if item['title'] == '-':
			self.menu.addSeparator()
			return
		action = self.menu.addAction(item['title'])
		if 'icon' in item:
			if len(item['icon']) < 3:
				action.setText(item['icon'] + ' ' + item['title'])
			elif len(item['icon']) in (64, 86):
				data = await blobstore.retrieve_blob(self.rpc, 'pb', 'pb', item['icon'], 10, cache=True)
				#action.setIcon(QtGui.QIcon(data))
				img = QtGui.QImage()
				img.loadFromData(data)
				action.setIcon(QtGui.QIcon(QtGui.QPixmap.fromImage(img)))
			else:
				action.setIcon(QtGui.QIcon(item['icon']))
		if 'exec' in item or 'func' in item or 'http_get' in item or 'rpc' in item:
			@asyncSlot()
			async def _onclick(_):
				await self.doAction(item)
			action.triggered.connect(_onclick)
		else:
			action.setDisabled(True)

	@async_debounce(0.5)
	async def refreshMenu(self):
		self.menuItems = []
		self.menu.clear()
		try:
			doc = self.get_journal_doc_id()
			if self.db and doc:
				nowplaying = list(await self.db.search(
					doc_id=doc,
					filter=lambda item: item.get('icon') in ('🔜','🔛') or item.get('cal'),
					order_by='y'
				))
				for idx, item in enumerate(nowplaying):
					await self.add_item(idx, { 'title': item.get('text'), 'icon': item.get('icon') })
				if len(nowplaying):
					self.menu.addSeparator()
		except Exception as e:
			logging.exception(e)
			pass

		try:
			for idx, item in enumerate(self.config['menu']):
				await self.add_item(idx, item)
		except Exception as e:
			logging.exception(e)
			pass

		try:
			doc = self.config.get("settings_doc")
			if self.db and doc:
				for idx, item in enumerate(await self.db.search(
					doc_id=doc,
					filter=lambda item: item.get('opt') == 'menu',
					order_by='y'
				)):
					await self.add_item(idx, item)
		except Exception as e:
			logging.exception(e)
			pass
		
		
		self.menu.addSeparator()
		action = self.menu.addAction("↪️ Relaunch")
		action.triggered.connect(lambda: self.run_cmd({'exec': 'sh -c "'+sys.argv[0]+' & kill '+str(os.getpid())+'"'}))
		action = self.menu.addAction("Exit")
		action.triggered.connect(self.exit)

	async def doAction(self, item):
		print("running",item)
		if 'func' in item:
			item['func'](self)
		elif 'rpc' in item:
			try:
				result = await self.rpc.caller._call(RpcOp.METHODCALL, item['rpc'][0], item['rpc'][1], item['rpc'][2], item['rpc'][3], item['rpc'][4], {}, item.get('timeout', 10))
				if result and not item.get('no_output'):
					self.show_info(repr(result))
			except Exception as e:
				self.show_error(str(e))
		else:
			self.run_cmd(item)

	def run_cmd(self, item):
		try:
			self.wnd = OutWnd(item, self.config)
		except Exception as e:
			print(e)
			self.show_error(str(e))

	@asyncSlot()
	async def configChanged(self, new_config):
		print("Updating menu", len(new_config))
		self.config = json.loads(new_config)
		doc = self.config.get("settings_doc")
		if doc and self.db:
			await self.db.fetch_doc(doc)
		await self.refreshMenu()

	@pyqtSlot()
	def show_info(self, info):
		def _do():
			QtWidgets.QMessageBox.information(self.parent(), "Success", info)
		QtCore.QTimer.singleShot(0, _do)

	@pyqtSlot()
	def show_error(self, info):
		def _do():
			QtWidgets.QMessageBox.warning(self.parent(), "Error", info)
		QtCore.QTimer.singleShot(0, _do)

	def __init__(self, icon, parent=None):
		super().__init__(icon, parent)
		self.menu = QtWidgets.QMenu(self.parent())
		action = self.menu.addAction("Exit")
		action.triggered.connect(self.exit)
		self.setContextMenu(self.menu)
		self.config = {}
		self.activated.connect(self.on_activated)
		self.db = None
		load_file_watch(self, getConfigPath(), self.configChanged)
		asyncio.ensure_future(self.connect_rpc())

	async def on_remote_item_updated(self, doc, items):
		if (doc == self.config.get('settings_doc') and any(item.get('opt') == 'menu' for item in items)) \
				or doc == self.get_journal_doc_id():
			await self.refreshMenu()

	def get_journal_doc_id(self):
		doc = self.config.get("journal_doc")
		if doc:
			return datetime.now().strftime(doc)

	async def connect_rpc(self):
		self.rpc = autoconnect_from_env()
		await self.rpc.connect()
		
		self.db = DocDb(self.rpc)
		self.db.remote_item_updated.on(self.on_remote_item_updated)
		doc = self.config.get("settings_doc")
		if doc:
			await self.db.fetch_doc(doc)
		doc = self.get_journal_doc_id()
		if doc:
			await self.db.fetch_doc(doc)

		while True:
			event = await self.rpc.server_events.get()
			if event.event_name == 'chat_event' or event.event_name == 'notification':
				chat = event.args[0]
				message = chat.get("message", "")
				title = chat.get("title", f"message from {chat.get("from")}")
				icon = chat.get("icon")
				icon = {"warning": SystemTrayIcon.Warning, "info": SystemTrayIcon.Information, "critical": SystemTrayIcon.Critical, "": SystemTrayIcon.NoIcon}.get(icon, SystemTrayIcon.Warning)
				self.showMessage(title, message, icon)
			elif event.event_name == 'doc_event':
				doc_id, items = event.args
				await self.db._update_doc(doc_id, items)
			#else:
				#self.showMessage("Event received: %s.%s.%s.%s" % (event.node, event.object, event.interface, event.event_name), repr(event.args), SystemTrayIcon.Warning)

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


import logging
from easyrpc.helpers import CustomLogFormatter
logging.basicConfig(level=logging.DEBUG)
logging.root.handlers[0].setFormatter(CustomLogFormatter())

def main():
	image='rainbow_1f308.png'
	app = QApplication(sys.argv)
	
	event_loop = QEventLoop(app)
	asyncio.set_event_loop(event_loop)
	app_close_event = asyncio.Event()
	app.aboutToQuit.connect(app_close_event.set)

	app.setQuitOnLastWindowClosed(False)
	w = QtWidgets.QWidget()
	trayIcon = SystemTrayIcon(QtGui.QIcon(image), w)
	trayIcon.show()

	with event_loop:
		event_loop.run_until_complete(app_close_event.wait())


if __name__ == '__main__':
	main()
