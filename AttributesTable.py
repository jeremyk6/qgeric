# -*- coding: utf-8 -*-

# Qgeric: plugin that makes graphical queries easier.
# Author: Jérémy Kalsron
#         jeremy.kalsron@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys
from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QPushButton, QIcon, QTableWidgetItem, QFileDialog, QToolBar, QAction, QApplication, QColor, QHeaderView, QInputDialog, QComboBox, QLineEdit, QMenu, QWidgetAction, QMessageBox
from PyQt4.QtCore import Qt, QSize, QTranslator, SIGNAL, QCoreApplication, QVariant
from qgis.core import *
from qgis.gui import *
from functools import partial
import odswriter as ods
import resources

# Display and export attributes from all active layers
class AttributesTable(QtGui.QWidget):
    def __init__(self, iface):
        QtGui.QWidget.__init__(self)
        
        self.setWindowTitle(self.tr('Search results'))
        self.resize(480,320)
        self.setMinimumSize(320,240)
        self.center()
        
        # Results export button
        btn_saveTab = QAction(QIcon(':/plugins/qgeric/resources/icon_save.png'), self.tr('Save this tab\'s results'), self)
        btn_saveTab.triggered.connect(self.handler_saveAttributes)
        btn_saveAllTabs = QAction(QIcon(':/plugins/qgeric/resources/icon_saveAll.png'), self.tr('Save all results'), self)
        btn_saveAllTabs.triggered.connect(self.handler_saveAllAttributes)   
        btn_zoom = QAction(QIcon(':/plugins/qgeric/resources/icon_Zoom.png'), self.tr('Zoom to selected attributes'), self)
        btn_zoom.triggered.connect(self.zoomToFeature) 
        btn_rename = QAction(QIcon(':/plugins/qgeric/resources/icon_Settings.png'), self.tr('Settings'), self)
        btn_rename.triggered.connect(self.renameWindow) 
                
        self.tabWidget = QtGui.QTabWidget() # Tab container
        self.connect(self.tabWidget, SIGNAL("currentChanged(int)"), self.tabChanged)
        
        self.loadingWindow = QtGui.QProgressDialog()
        self.loadingWindow.setWindowTitle(self.tr('Loading...'))
        self.loadingWindow.setRange(0,100)
        self.loadingWindow.setAutoClose(False)
        self.loadingWindow.setCancelButton(None)
        
        self.canvas = iface.mapCanvas()
        iface.connect(self.canvas, SIGNAL("extentsChanged()"), self.highlight_features)
        self.highlight = []
        self.highlight_rows = []
        
        toolbar = QToolBar()
        toolbar.addAction(btn_saveTab)
        toolbar.addAction(btn_saveAllTabs)
        toolbar.addSeparator()
        toolbar.addAction(btn_zoom)
        toolbar.addSeparator()
        toolbar.addAction(btn_rename)

        vbox = QtGui.QVBoxLayout()
        vbox.setContentsMargins(0,0,0,0)
        vbox.addWidget(toolbar)
        vbox.addWidget(self.tabWidget)
        self.setLayout(vbox)
        
    def renameWindow(self):
        title, ok = QInputDialog.getText(self, self.tr('Rename window'), self.tr('Enter a new title:'))  
        if ok:
            self.setWindowTitle(title)
        
    def tabChanged(self, index):
        self.highlight_features()
        
    def highlight_features(self):
        del self.highlight[:]
        del self.highlight_rows[:]
        index = self.tabWidget.currentIndex()
        if self.tabWidget.count() != 0:
            table = self.tabWidget.widget(index).findChildren(QtGui.QTableWidget)[0]
            items = table.selectedItems()
            for item in items:
                highlight = QgsHighlight(self.canvas, item.feature.geometry().centroid(), self.tabWidget.widget(index).layer)
                highlight.setColor(QColor(255,0,0))
                if item.row() not in self.highlight_rows:
                    self.highlight.append(highlight)
                    self.highlight_rows.append(item.row())
            
    
    def tr(self, message):
        return QCoreApplication.translate('Qgeric', message)
        
    def zoomToFeature(self):
        index = self.tabWidget.currentIndex()
        table = self.tabWidget.widget(index).findChildren(QtGui.QTableWidget)[0]
        items = table.selectedItems()
        feat_id = []
        for item in items:
            feat_id.append(item.feature.id())
        if len(feat_id) >= 1:
            if len(feat_id) == 1:
                self.canvas.setExtent(items[0].feature.geometry().buffer(5, 0).boundingBox()) # in case of a single point, it will still zoom to it
            else:
                self.canvas.zoomToFeatureIds(self.tabWidget.widget(self.tabWidget.currentIndex()).layer, feat_id)         
        self.canvas.refresh() 
    
    # Add a new tab
    def addLayer(self, layer, headers, types, features):
        tab = QtGui.QWidget()
        tab.layer = layer
        p1_vertical = QtGui.QVBoxLayout(tab)
        p1_vertical.setContentsMargins(0,0,0,0)
        
        table = QtGui.QTableWidget();
        self.connect(table, SIGNAL("itemSelectionChanged()"), self.selectionChanged)
        table.title = layer.name()
        table.setColumnCount(len(headers))
        if len(features) > 0:
            table.setRowCount(len(features))
            nbrow = len(features)
            self.loadingWindow.show()
            self.loadingWindow.setLabelText(table.title)
            self.loadingWindow.activateWindow();
            self.loadingWindow.showNormal();
            
            # Table population
            m = 0
            for feature in features:
                n = 0
                for cell in feature.attributes():
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, cell)
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    item.feature = feature
                    table.setItem(m, n, item)
                    n += 1
                m += 1
                self.loadingWindow.setValue(int((float(m)/nbrow)*100))  
                QApplication.processEvents()
            
        else:
            table.setRowCount(0)  
                            
        table.setHorizontalHeaderLabels(headers)
        
        table.types = types
        table.filter_op = []
        table.filters = []
        for i in range(0, len(headers)):
            table.filters.append('')
            table.filter_op.append(0)
        
        header = table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(partial(self.filterMenu, table))
            
        table.setSortingEnabled(True)
        
        p1_vertical.addWidget(table)
        
        title = table.title
        # We reduce the title's length to 20 characters
        if len(title)>20:
            title = title[:20]+'...'
        
        # We add the number of elements to the tab's title.
        title += ' ('+str(len(features))+')'
            
        self.tabWidget.addTab(tab, title) # Add the tab to the conatiner
        self.tabWidget.setTabToolTip(self.tabWidget.indexOf(tab), table.title) # Display a tooltip with the layer's full name
     
    def filterMenu(self, table, pos):
        index = table.columnAt(pos.x())
        menu = QMenu()
        filter_operation = QComboBox()
        if table.types[index] in [10, 14, 15, 16]:
            filter_operation.addItems([self.tr('Contains'),self.tr('Equals')])
        else:
            filter_operation.addItems(['=','>','<'])
        filter_operation.setCurrentIndex(table.filter_op[index])
        action_filter_operation = QWidgetAction(self)
        action_filter_operation.setDefaultWidget(filter_operation)
        filter_value = QLineEdit(table.filters[index])
        action_filter_value = QWidgetAction(self)
        action_filter_value.setDefaultWidget(filter_value)
        menu.addAction(action_filter_operation)
        menu.addAction(action_filter_value)
        action_filter_apply = QAction(self.tr('Apply'), self)
        action_filter_apply.triggered.connect(partial(self.applyFilter, table, index, filter_value, filter_operation))
        menu.addAction(action_filter_apply)
        menu.exec_(QtGui.QCursor.pos())
     
    def applyFilter(self, table, index, filter_value, filter_operation):
        table.filters[index] = filter_value.text()
        table.filter_op[index] = filter_operation.currentIndex()
        nb_elts = 0
        for i in range(0, table.rowCount()):
            table.setRowHidden(i, False)
            nb_elts += 1
        hidden_rows = []
        for nb_col in range(0, table.columnCount()):
            filtered = False
            header = table.horizontalHeaderItem(nb_col).text()
            if table.filters[nb_col].strip():
                filtered = True
                items = None
                if table.types[nb_col] in [10, 14, 15, 16]: # If it's a string
                    type = None
                    if table.filter_op[nb_col] == 0: # Contain
                        type = Qt.MatchContains
                    if table.filter_op[nb_col] == 1: # Equal
                        type = Qt.MatchFixedString 
                    items = table.findItems(table.filters[nb_col], type)
                else: # If it's a number
                    items = []
                    for nb_row in range(0, table.rowCount()):
                        item = table.item(nb_row, nb_col)
                        if item.text().strip():
                            if table.filter_op[nb_col] == 0: # =
                                if  float(item.text()) == float(table.filters[nb_col]):
                                    items.append(item)
                            if table.filter_op[nb_col] == 1: # >
                                if  float(item.text()) > float(table.filters[nb_col]):
                                    items.append(item)
                            if table.filter_op[nb_col] == 2: # <
                                if  float(item.text()) < float(table.filters[nb_col]):
                                    items.append(item)
                rows = []
                for item in items:
                    if item.column() == nb_col:
                        rows.append(item.row())
                for i in range(0, table.rowCount()):
                    if i not in rows:
                        if i not in hidden_rows:
                            nb_elts -= 1
                        table.setRowHidden(i, True)
                        hidden_rows.append(i)
            if filtered:
                if header[len(header)-1] != '*':
                    table.setHorizontalHeaderItem(nb_col, QTableWidgetItem(header+'*'))
            else:
                if header[len(header)-1] == '*':
                    header = header[:-1]
                    table.setHorizontalHeaderItem(nb_col, QTableWidgetItem(header))
        
        title = self.tabWidget.tabText(self.tabWidget.currentIndex())
        for i in reversed(range(len(title))):
            if title[i] == ' ':
                break
            title = title[:-1]
        title += '('+str(nb_elts)+')'
        self.tabWidget.setTabText(self.tabWidget.currentIndex(), title)
        
        
    def selectionChanged(self):
        self.highlight_features()
        
    def handler_saveAttributes(self):
        self.saveAttributes(True)
        
    def handler_saveAllAttributes(self):
        self.saveAttributes(False)
       
    # Save tables in OpenDocument format
    # Use odswriter library
    def saveAttributes(self, active):
        file = QFileDialog.getSaveFileName(self, self.tr('Save in...'),'', self.tr('OpenDocument Spreadsheet (*.ods)'))
        if file:
            with ods.writer(open(file,"wb")) as odsfile:
                tabs = None
                if active:
                    tabs = self.tabWidget.currentWidget().findChildren(QtGui.QTableWidget)
                else:
                    tabs = self.tabWidget.findChildren(QtGui.QTableWidget)
                for table in reversed(tabs):
                    sheet = odsfile.new_sheet(table.title[:20]+'...') # For each tab in the container, a new sheet is created
                    sheet.writerow([table.title]) # As the tab's title's lenght is limited, the full name of the layer is written in the first row
                    nb_row = table.rowCount()
                    nb_col = table.columnCount()
                    
                    # Fetching and writing of the table's header
                    header = []
                    for i in range(0,nb_col):
                        header.append(table.horizontalHeaderItem(i).text())
                    sheet.writerow(header)
                    
                    # Fetching and writing of the table's items
                    for i in range(0,nb_row):
                        row = []
                        for j in range(0,nb_col):
                            row.append(table.item(i,j).text())
                        if not table.isRowHidden(i):
                            sheet.writerow(row)
    
    def center(self):
        screen = QtGui.QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width()-size.width())/2, (screen.height()-size.height())/2)
        
    def clear(self):
        self.tabWidget.clear()
        for table in self.tabWidget.findChildren(QtGui.QTableWidget):
            table.setParent(None)
        
    def closeEvent(self, e):
        result = QMessageBox.question(self, self.tr("Saving ?"), self.tr("Would you like to save results before exit ?"), buttons = QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if result == QMessageBox.Yes:
            self.saveAttributes(False)
            self.clear()
            e.accept()
        elif result == QMessageBox.No:
            self.clear()
            e.accept()
        else:
            e.ignore()
        
    def closeLoading(self):
        self.loadingWindow.close()