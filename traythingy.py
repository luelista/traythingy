#!/usr/bin/env python3
import sys, os, json
from PyQt5 import QtWidgets, QtCore, QtGui
import os.path
import runpy
import subprocess
#from Cocoa import *

from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciLexerCPP

def getConfigPath():
	home = os.path.expanduser("~")
	return os.path.join(home, ".config/traythingy.json")


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


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
	def initMenu(self, configCode):
		self.menu = QtWidgets.QMenu(self.parent())
		self.menuItems = []
		
		self.config = json.loads(configCode)
		for idx,item in enumerate(self.config['menu']):
			if item['name'] == '-':
				self.menu.addSeparator()
				continue
			action = self.menu.addAction(item['name'])
			if 'icon' in item:
				action.setIcon(QtGui.QIcon(item['icon']))
			if 'exec' in item or 'func' in item or 'http_get' in item:
				action.triggered.connect(lambda c,idx=idx: self.doAction(idx))
			else:
				action.setDisabled(True)

		self.menu.addSeparator()
		action = self.menu.addAction("↪️ Relaunch")
		action.triggered.connect(lambda: self.run_cmd({'exec': 'sh -c "'+sys.argv[0]+' & kill '+str(os.getpid())+'"'}))
		action = self.menu.addAction("Exit")
		action.triggered.connect(self.exit)
		
		self.setContextMenu(self.menu)

	def doAction(self, idx):
		item = self.config['menu'][idx]
		print("running",idx,item)
		if 'func' in item:
			item['func'](self)
		else:
			self.run_cmd(item)

	def run_cmd(self, item):
		try:
			self.wnd = OutWnd(item, self.config)
		except Exception as e:
			print(e)
			QtWidgets.QMessageBox.warning(self.parent(), "Error", str(e))

	def __init__(self, icon, parent=None):
		super().__init__(icon, parent)
		self.config = {}
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



class RpcTransport:
	def __init__(self, handler):
		self.peers = list()
		self.handler = handler
	async def advertise(self, meta):
		pass
	async def getSelfAddresses(self):
		return []
	async def findPeerConnections(self, peer_id):
		pass

class UdpSimpleRpcTransport(RpcTransport):
	DUMMY_SESSION = b"\0"*12
	def __init__(self, handler, bindAddress):
		super().__init__(handler)
		self._drain_lock = asyncio.Lock(loop=handler.loop)
		self.bindHost, self.bindPort = UdpSimpleRpcTransport.parseAddress(bindAddress)
		self.connections = dict()
		self.waiting_for_peer = list()

	@staticmethod
	def parseAddress(adr):
		match = re.match("/ip/([^/]+)/udp/(\d+)", adr)
		return (match.group(1), int(match.group(2)))

	async def getSelfAddresses(self):
		return ["/ip/%s/udp/%d"% (ip, self.bindPort) for ip in [self.bindHost]]

	async def advertise(self, meta):
		enc_msg = self.encrypt_adv_msg(meta)
		self.asyncio_transport.sendto(UdpSimpleRpcTransport.DUMMY_SESSION + enc_msg,
									  ("255.255.255.255", self.bindPort))

	def encrypt_adv_msg(self, meta):
		raw_msg = xdrm.dumps(meta)
		signed_msg = self.handler.keypair.sign(raw_msg)
		return pyhy.hydro_secretbox_encrypt(signed_msg, 0, CTX, self.handler.netkey)

	async def findPeerConnections(self, peer_id):
		enc_msg = self.encrypt_adv_msg({"id": self.handler.pk, "find":peer_id})
		self.asyncio_transport.sendto(UdpSimpleRpcTransport.DUMMY_SESSION + enc_msg,
									  ("255.255.255.255", self.bindPort))

	async def connect(self, addr):
		return self.make_connection(UdpSimpleRpcTransport.parseAddress(addr))

	async def run(self):
		transport, protocol = await self.handler.loop.create_datagram_endpoint(lambda: self,
												   local_addr=(self.bindHost,self.bindPort),
								  reuse_address=True, reuse_port=True, allow_broadcast=True)

	def connection_made(self, transport):
		self.asyncio_transport = transport

	def make_connection(self, addr):
		try:
			return self.connections[addr]
		except KeyError:
			self.connections[addr] = UdpRpcConnection(self, addr)

	def datagram_received(self, datagram_bytes, addr):
		session_id, frame = datagram_bytes[0:12], datagram_bytes[12:]
		print('Received %r from %s' % (session_id, addr))
		if session_id == UdpSimpleRpcTransport.DUMMY_SESSION:
			dec_datagram_bytes = pyhy.hydro_secretbox_decrypt(frame, 0, CTX, self.handler.netkey)

			data = sign_unpack(dec_datagram_bytes)
			data['adr'].append("/ip/%s/udp/%d" % addr)
			self.handler.handleAdvertise(data)
		else:
			conn = self.make_connection(addr)
			self.handler.handleData(session_id, frame, conn)
		#
		#print('Send %r to %s' % (message, addr))
		#self.asyncio_transport.sendto(data, addr)

	def error_received(self, exc):
		print("Error in UdpSimpleRpcTransport")
		print(exc)






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
