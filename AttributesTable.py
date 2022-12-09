# Qgeric: Graphical queries by drawing simple shapes.
# Author: Jérémy Kalsron
#         jeremy.kalsron@gmail.com

# Adds : Francois Thevand
#        francois.thevand@gmail.com

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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys
from qgis.PyQt import QtGui, QtCore
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import Qt, QSize, QDate, QTime, QDateTime, QTranslator, QCoreApplication, QVariant

from qgis.PyQt.QtWidgets import (QWidget, QDesktopWidget, QTabWidget, QVBoxLayout, QProgressDialog, 
                                QStatusBar, QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, 
                                QToolBar, QAction, QApplication, QHeaderView, QInputDialog, QComboBox, 
                                QLineEdit, QMenu, QWidgetAction, QMessageBox, QDateEdit, QTimeEdit, QDateTimeEdit)
from qgis.core import QgsWkbTypes, QgsVectorLayer, QgsProject, QgsLayerTreeGroup, QgsGeometry, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.gui import QgsMessageBar, QgsHighlight
from qgis.utils import *
from functools import partial
from . import odswriter as ods
from . import resources

# Display and export attributes from all active layers
class AttributesTable(QWidget):
    def __init__(self, iface):
        QWidget.__init__(self)
        
        self.setWindowTitle(self.tr('Search results'))
        self.resize(480,320)
        self.setMinimumSize(320,240)
        self.center()
        
        # Results export button
        self.btn_saveTab = QAction(QIcon(':/plugins/qgeric/resources/icon_save.png'), self.tr('Save this tab\'s results'), self)
        self.btn_saveTab.triggered.connect(lambda : self.saveAttributes(True))
        self.btn_saveAllTabs = QAction(QIcon(':/plugins/qgeric/resources/icon_saveAll.png'), self.tr('Save all results'), self)
        self.btn_saveAllTabs.triggered.connect(lambda : self.saveAttributes(False))
        self.btn_export = QAction(QIcon(':/plugins/qgeric/resources/icon_export.png'), self.tr('Export the selection as a memory layer'), self)
        self.btn_export.triggered.connect(self.exportLayer)
        self.btn_zoom = QAction(QIcon(':/plugins/qgeric/resources/icon_Zoom.png'), self.tr('Zoom to selected attributes'), self)
        self.btn_zoom.triggered.connect(self.zoomToFeature)
        self.btn_selectGeom = QAction(QIcon(':/plugins/qgeric/resources/icon_HlG.png'), self.tr('Highlight feature\'s geometry'), self)
        self.btn_selectGeom.triggered.connect(self.selectGeomChanged)
        self.btn_rename = QAction(QIcon(':/plugins/qgeric/resources/icon_Settings.png'), self.tr('Settings'), self)
        self.btn_rename.triggered.connect(self.renameWindow)
                
        self.tabWidget = QTabWidget() # Tab container
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.currentChanged.connect(self.highlight_features)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)
        
        self.loadingWindow = QProgressDialog()
        self.loadingWindow.setWindowTitle(self.tr('Loading...'))
        self.loadingWindow.setRange(0,100)
        self.loadingWindow.setAutoClose(False)
        self.loadingWindow.setCancelButton(None)

        self.project = QgsProject.instance()
        self.root = self.project.layerTreeRoot()

        self.canvas = iface.mapCanvas()
        self.canvas.extentsChanged.connect(self.highlight_features)
        self.highlight = []
        self.highlight_rows = []
        
        toolbar = QToolBar()
        toolbar.addAction(self.btn_saveTab)
        toolbar.addAction(self.btn_saveAllTabs)
        toolbar.addAction(self.btn_export)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_zoom)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_selectGeom)
        toolbar.addAction(self.btn_rename)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0,0,0,0)
        vbox.addWidget(toolbar)
        vbox.addWidget(self.tabWidget)
        self.setLayout(vbox)
        
        self.mb = iface.messageBar()
        
        self.selectGeom = False # False for point, True for geometry

    def renameWindow(self):
        title, ok = QInputDialog.getText(self, self.tr('Rename window'), self.tr('Enter a new title:'))  
        if ok:
            self.setWindowTitle(title)
            
    def closeTab(self, index):
        self.tabWidget.widget(index).deleteLater()
        self.tabWidget.removeTab(index)
        
    def selectGeomChanged(self):
        if self.selectGeom:
            self.selectGeom = False
            self.btn_selectGeom.setText(self.tr('Highlight feature\'s geometry'))
            self.btn_selectGeom.setIcon(QIcon(':/plugins/qgeric/resources/icon_HlG.png'))
        else:
            self.selectGeom = True
            self.btn_selectGeom.setText(self.tr('Highlight feature\'s centroid'))
            self.btn_selectGeom.setIcon(QIcon(':/plugins/qgeric/resources/icon_HlC.png'))
        self.highlight_features()

    def exportLayer(self):

        if self.tabWidget.count() != 0:
            index = self.tabWidget.currentIndex()
            table = self.tabWidget.widget(index).findChildren(QTableWidget)[0]
            items = table.selectedItems()
            if len(items) > 0:
                type = ''
                if items[0].feature.geometry().type() == QgsWkbTypes.PointGeometry:
                    type = 'Point'
                elif items[0].feature.geometry().type() == QgsWkbTypes.LineGeometry:
                    type = 'LineString'
                else:
                    type = 'Polygon'
                features = []
                for item in items:
                    if item.feature not in features:
                        features.append(item.feature)
                name = ''
                ok = True
                while not name.strip() and ok == True:
                    name, ok = QInputDialog.getText(self, self.tr('Layer name'), self.tr('Give a name to the layer:'))
                if ok:
                    layer = QgsVectorLayer(type+"?crs="+table.crs.authid(),name,"memory")
                    layer.startEditing()
                    layer.dataProvider().addAttributes(features[0].fields().toList())
                    layer.dataProvider().addFeatures(features)
                    layer.commitChanges()
                    if self.project.layerTreeRoot().findGroup(self.tr('Extracts')) is None:
                        self.project.layerTreeRoot().insertChildNode(0, QgsLayerTreeGroup(self.tr('Extracts')))
                    group = self.project.layerTreeRoot().findGroup(self.tr('Extracts'))
                    self.project.addMapLayer(layer, False)
                    iface.layerTreeView().refreshLayerSymbology(layer.id())
                    iface.mapCanvas().refresh()
                    group.insertLayer(0, layer)
                    group.setExpanded(True)

            else:
                self.mb.pushWarning(self.tr('Warning'), self.tr('There is no selected feature !'))
        
    def highlight_features(self):
        for item in self.highlight:
            self.canvas.scene().removeItem(item)
        del self.highlight[:]
        del self.highlight_rows[:]
        index = self.tabWidget.currentIndex()
        tab = self.tabWidget.widget(index)
        if self.tabWidget.count() != 0:
            table = self.tabWidget.widget(index).findChildren(QTableWidget)[0]
            nb = 0
            area = 0
            length = 0
            items = table.selectedItems()
            for item in items:
                if item.row() not in self.highlight_rows:
                    if self.selectGeom:
                        highlight = QgsHighlight(self.canvas, item.feature.geometry(), self.tabWidget.widget(index).layer)
                    else:
                        highlight = QgsHighlight(self.canvas, item.feature.geometry().centroid(), self.tabWidget.widget(index).layer)
                    highlight.setColor(QColor(255,0,0))
                    self.highlight.append(highlight)
                    self.highlight_rows.append(item.row())
                    g = QgsGeometry(item.feature.geometry())
                    g.transform(QgsCoordinateTransform(tab.layer.crs(), QgsCoordinateReferenceSystem(2154), QgsProject.instance())) # geometry reprojection to get meters
                    nb += 1
                    area += g.area()
                    length += g.length()
            if tab.layer.geometryType()==QgsWkbTypes.PolygonGeometry:
                tab.sb.showMessage(self.tr('Selected features')+': '+str(nb)+'  '+self.tr('Area')+': '+"%.2f"%area+' m'+u'²')
            elif tab.layer.geometryType()==QgsWkbTypes.LineGeometry:
                tab.sb.showMessage(self.tr('Selected features')+': '+str(nb)+'  '+self.tr('Length')+': '+"%.2f"%length+' m')
            else:
                tab.sb.showMessage(self.tr('Selected features')+': '+str(nb))
    
    def tr(self, message):
        return QCoreApplication.translate('Qgeric', message)
        
    def zoomToFeature(self):
        index = self.tabWidget.currentIndex()
        table = self.tabWidget.widget(index).findChildren(QTableWidget)[0]
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
        tab = QWidget()
        tab.layer = layer
        p1_vertical = QVBoxLayout(tab)
        p1_vertical.setContentsMargins(0,0,0,0)
        
        table = QTableWidget()
        table.itemSelectionChanged.connect(self.highlight_features)
        table.title = layer.name()
        table.crs = layer.crs()
        table.setColumnCount(len(headers))
        if len(features) > 0:
            table.setRowCount(len(features))
            nbrow = len(features)
            self.loadingWindow.show()
            self.loadingWindow.setLabelText(table.title)
            self.loadingWindow.activateWindow()
            self.loadingWindow.showNormal()
            
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
        table.horizontalHeader().setSectionsMovable(True)
        
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
        
        # Status bar to display informations (ie: area)
        tab.sb = QStatusBar()
        p1_vertical.addWidget(tab.sb)
        
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
        if table.types[index] in [10]:
            filter_operation.addItems([self.tr('Contains'),self.tr('Equals')])
        else:
            filter_operation.addItems(['=','>','<'])
        filter_operation.setCurrentIndex(table.filter_op[index])
        action_filter_operation = QWidgetAction(self)
        action_filter_operation.setDefaultWidget(filter_operation)
        if table.types[index] in [14]:
            if not isinstance(table.filters[index], QDate):
                filter_value = QDateEdit()
            else:
                filter_value = QDateEdit(table.filters[index])
        elif table.types[index] in [15]:
            if not isinstance(table.filters[index], QTime):
                filter_value = QTimeEdit()
            else:
                filter_value = QTimeEdit(table.filters[index])
        elif table.types[index] in [16]:
            if not isinstance(table.filters[index], QDateTime):
                filter_value = QDateTimeEdit()
            else:
                filter_value = QDateTimeEdit(table.filters[index])
        else:
            filter_value = QLineEdit(table.filters[index])
        action_filter_value = QWidgetAction(self)
        action_filter_value.setDefaultWidget(filter_value)
        menu.addAction(action_filter_operation)
        menu.addAction(action_filter_value)
        action_filter_apply = QAction(self.tr('Apply'), self)
        action_filter_apply.triggered.connect(partial(self.applyFilter, table, index, filter_value, filter_operation))
        action_filter_cancel = QAction(self.tr('Cancel'), self)
        action_filter_cancel.triggered.connect(partial(self.applyFilter, table, index, None, filter_operation))
        menu.addAction(action_filter_apply)
        menu.addAction(action_filter_cancel)
        menu.exec_(QtGui.QCursor.pos())
     
    def applyFilter(self, table, index, filter_value, filter_operation):
        if filter_value == None:
            table.filters[index] = None
        else:
            if isinstance(filter_value, QDateEdit):
                table.filters[index] = filter_value.date()
            elif isinstance(filter_value, QTimeEdit):
                table.filters[index] = filter_value.time()
            elif isinstance(filter_value, QDateTimeEdit):
                table.filters[index] = filter_value.dateTime()
            else:
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
            valid = False
            if table.filters[nb_col] is not None:
                if  type(table.filters[nb_col]) in [QDate, QTime, QDateTime]:
                    valid = True
                else:
                    if table.filters[nb_col].strip():
                        valid = True
            if valid:
                filtered = True
                items = None
                if table.types[nb_col] in [10]:# If it's a string
                    filter_type = None
                    if table.filter_op[nb_col] == 0: # Contain
                        filter_type = Qt.MatchContains
                    if table.filter_op[nb_col] == 1: # Equal
                        filter_type = Qt.MatchFixedString 
                    items = table.findItems(table.filters[nb_col], filter_type)
                elif table.types[nb_col] in [14, 15, 16]: # If it's a date/time
                    items = []
                    for nb_row in range(0, table.rowCount()):
                        item = table.item(nb_row, nb_col)
                        if table.filter_op[nb_col] == 0: # =
                            if  item.data(QTableWidgetItem.Type) == table.filters[nb_col]:
                                items.append(item)
                        if table.filter_op[nb_col] == 1: # >
                            if  item.data(QTableWidgetItem.Type) > table.filters[nb_col]:
                                items.append(item)
                        if table.filter_op[nb_col] == 2: # <
                            if  item.data(QTableWidgetItem.Type) < table.filters[nb_col]:
                                items.append(item)
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
       
    # Save tables in OpenDocument format
    # Use odswriter library
    def saveAttributes(self, active):
        # Création d'un sous-dossier "Extractions" dans le dossier contenant le projet
        os.makedirs(self.project.homePath() + '/Extractions', exist_ok=True)
        file = QFileDialog.getSaveFileName(self, self.tr('Save in...'),self.project.homePath() + '/Extractions', self.tr('OpenDocument Spreadsheet (*.ods)'))
        if file[0]:
            try:
                with ods.writer(open(file[0],"wb")) as odsfile:
                    tabs = None
                    if active:
                        tabs = self.tabWidget.currentWidget().findChildren(QTableWidget)
                    else:
                        tabs = self.tabWidget.findChildren(QTableWidget)
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
                    return True
            except IOError:
                QMessageBox.critical(self, self.tr('Error'), self.tr('The file can\'t be written.')+'\n'+self.tr('Maybe you don\'t have the rights or are trying to overwrite an opened file.'))
                return False
    
    def center(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width()-size.width())/2, (screen.height()-size.height())/2)
        
    def clear(self):
        self.tabWidget.clear()
        for table in self.tabWidget.findChildren(QTableWidget):
            table.setParent(None)
        
    def closeEvent(self, e):
        result = QMessageBox.question(self, self.tr("Saving ?"), self.tr("Would you like to save results before exit ?"), buttons = QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if result == QMessageBox.Yes:
            if self.saveAttributes(False):
                self.clear()
                e.accept()
            else:
                e.ignore()
        elif result == QMessageBox.No:
            self.clear()
            e.accept()
        else:
            e.ignore()
