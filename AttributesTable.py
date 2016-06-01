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
from PyQt4.QtGui import QPushButton, QIcon, QTableWidgetItem, QFileDialog, QToolBar, QAction, QApplication, QColor, QHeaderView
from PyQt4.QtCore import Qt, QSize, QTranslator, SIGNAL, QCoreApplication
from qgis.core import *
from qgis.gui import *
from functools import partial
import odswriter as ods
import resources

# Display and export attributes from all active layers
class AttributesTable(QtGui.QWidget):
    def __init__(self, iface):
        QtGui.QWidget.__init__(self)
        
        self.setWindowTitle(self.tr('Attributes table'))
        self.resize(480,320)
        self.setMinimumSize(320,240)
        self.center()
        
        # Results export button
        btn_saveAllTabs = QPushButton(QIcon(':/plugins/qgeric/resources/icon_save.png'), self.tr('Save results'), self)
        btn_saveAllTabs.clicked.connect(self.handler_saveAllAttributes)
                
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

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.tabWidget)
        vbox.addWidget(btn_saveAllTabs)
        self.setLayout(vbox)
        
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
    def addLayer(self, layer, headers, features):
        tab = QtGui.QWidget()
        tab.layer = layer
        p1_vertical = QtGui.QVBoxLayout(tab)
        
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
                    cell = unicode(cell)
                    item = QTableWidgetItem(cell)
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
        table.setSortingEnabled(True)
        
        btn_saveTab = QAction(QIcon(':/plugins/qgeric/resources/icon_save.png'),self.tr('Save this tab\'s results'), self)
        btn_saveTab.triggered.connect(self.handler_saveAttributes)
        
        btn_zoom = QAction(QIcon(':/plugins/qgeric/resources/icon_Zoom.png'), self.tr('Zoom to selected attributes'), self)
        btn_zoom.triggered.connect(self.zoomToFeature) 
        
        toolbar = QToolBar()
        toolbar.addAction(btn_saveTab)
        toolbar.addAction(btn_zoom)
        toolbar.setIconSize(QSize(18,18))
        
        p1_vertical.addWidget(toolbar)
        p1_vertical.addWidget(table)
        
        title = table.title
        # We reduce the title's length to 20 characters
        if len(title)>20:
            title = title[:20]+'...'
            
        self.tabWidget.addTab(tab, title) # Add the tab to the conatiner
        self.tabWidget.setTabToolTip(self.tabWidget.indexOf(tab), table.title) # Display a tooltip with the layer's full name
        
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
        self.clear()
        self.emit(SIGNAL("ATclose()"))
        e.accept()
        
    def closeLoading(self):
        self.loadingWindow.close()