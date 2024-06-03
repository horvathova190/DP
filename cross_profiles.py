# -*- coding: utf-8 -*-
"""
/***************************************************************************
 -------------------
        Name                 : cross_profiles
        Begin                : 22/01/2024
        Copyright            : (C) 2024 by k_hor
        Email                : horvathova190@uniba.sk
        Description:         : This tool is based on Master's thesis: Creating of River Cross Profiles from Lidar Data.\
                               It integrates LAS files and vector files containing river data (line features) to generate cross-sectional profiles at specified intervals.\
                               These profiles are exported as PNG image files and displayed alongside a terrain map preview.

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QCoreApplication, QFileInfo
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterString, 
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterFile, 
                       QgsTextFormat,
                       QgsPalLayerSettings,
                       QgsVectorLayerSimpleLabeling,
                       QgsLayoutItemLabel,
                       QgsRectangle,
                       QgsPrintLayout,
                       QgsLayoutItemMap,
                       QgsLayoutPoint,
                       QgsLayoutSize,
                       QgsUnitTypes,
                       QgsLayoutExporter,
                       QgsTextBufferSettings, 
                       QgsRasterLayer,
                       QgsVectorLayer, 
                       QgsCoordinateReferenceSystem,
                       QgsPointCloudLayer, 
                       QgsProject,
                       QgsLineSymbol,
                       QgsSingleSymbolRenderer,
                       QgsProcessingException
                       )
from PyQt5.QtGui import QColor
from qgis import processing
import matplotlib.pyplot as plt
import geopandas as gpd
import os
from osgeo import gdal
import glob
import time



class CrossProfilesAlgorithm(QgsProcessingAlgorithm):

    INPUT_LAS_FOLDER = 'INPUT_LAS_FOLDER'
    LINE_INPUT = 'LINE_INPUT'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    Width = 'Width'
    Spacing = 'Spacing'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.INPUT_LAS_FOLDER,
            self.tr("Input LAS Folder"),
            behavior=QgsProcessingParameterFile.Folder))

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LINE_INPUT,
                self.tr('Line Input'),
                [QgsProcessing.TypeVectorLine]

            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.Width,
                self.tr('Width')
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.Spacing,
                self.tr('Spacing')
            )
        )
        self.addParameter(QgsProcessingParameterFile(
            self.OUTPUT_FOLDER,
            self.tr("Output Folder"),
            behavior=QgsProcessingParameterFile.Folder))

    def processAlgorithm(self, parameters, context, feedback):
        las_folder = self.parameterAsString(parameters, self.INPUT_LAS_FOLDER, context)
        line_path = self.parameterAsVectorLayer(parameters, self.LINE_INPUT, context)
        output_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        Width = int(self.parameterAsString(parameters, self.Width, context))
        Spacing = int(self.parameterAsString(parameters, self.Spacing, context))
        
        output_folder = output_folder.rstrip("\\") + "\\"

        #################################Checking CRS for inputs######################
        ## Get the first LAS file in the LAS folder
        
        las_files = glob.glob(os.path.join(las_folder, '*.las'))
        first_las_file = las_files[0]

        ## Checking CRS for inputs ##
        feedback.pushInfo("Checking CRS for inputs...")
        layer1_proj = QgsPointCloudLayer(first_las_file, 'merged.las', 'pdal')
        crs1 = layer1_proj.crs()
        crs3 = line_path.crs()
        
        #Checking if CRS matches
        if crs1 != crs3:
            feedback.pushInfo("CRS do not match: Input Point Cloud CRS: {} - Line Input CRS: {}".format(crs1.authid(), crs3.authid()))
            raise QgsProcessingException("CRS do not match between input LAS files and line input.")

        else:
            feedback.pushInfo("CRS do match: Input Point Cloud CRS: {} - Line Input CRS: {}".format(crs1.authid(), crs3.authid()))

        def format_time(elapsed_time):
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            return f"{minutes} minutes, {seconds} seconds"
        
        output_directory = QFileInfo(output_folder).path()

        #merging point cloud
        count_files = len(las_files)
        if count_files > 1:
            start_time_step1 = time.time()  # Start the timer for the processing step
            output_file = f'{output_directory}/merged.las' 
            feedback.pushInfo("Merging LAS files...")
            processing.run("LAStools:LasMergePro", {
                'INPUT_DIRECTORY': las_folder,
                'INPUT_WILDCARDS': '*.las',
                'FILES_ARE_FLIGHTLINES': False,
                'APPLY_FILE_SOURCE_ID': False,
                'OUTPUT_LASLAZ': output_file,
                'ADDITIONAL_OPTIONS': '',
                'VERBOSE': False,
                'CPU64': True,
                'GUI': False
            })
            elapsed_time_step1 = time.time() - start_time_step1
            feedback.pushInfo(f"Time elapsed for merging LAS files: {format_time(elapsed_time_step1)}")
        elif count_files == 1:
            output_file = las_files[0] 
            feedback.pushInfo("Only one LAS file found, skipping merging step.")    

        start_time_filter = time.time()  # Start the timer for the filtering step
        output_filter = f'{output_directory}/filter.las'
        feedback.pushInfo("Filtering LAS files...")
        processing.run("pdal:filter", {
            'INPUT': output_file,
            'FILTER_EXPRESSION':'Classification = 2 OR Classification = 9',
            'FILTER_EXTENT': None,
            'OUTPUT': output_filter
        })
        elapsed_time_filter = time.time() - start_time_filter
        feedback.pushInfo(f"Time elapsed for filtering LAS files: {format_time(elapsed_time_filter)}")
                    
        #Boundary of Point Cloud for cliping river and DTM
        boundary = f'{output_directory}/extracted_boundary.shp'
          
        processing.run("LAStools:LasBoundary", 
                       {'VERBOSE':False,'CPU64':False,'GUI':False,
                        'INPUT_LASLAZ':output_filter,
                        'FILTER_RETURN_CLASS_FLAGS1':0,'MODE':0,'CONCAVITY':50,'HOLES':True,'DISJOINT':True,
                        'LABELS':False,'OUTPUT_VECTOR':boundary,'ADDITIONAL_OPTIONS':''})
        
        #Assingnig projection for vector layer
        processing.run("qgis:definecurrentprojection", 
                       {'INPUT':boundary,
                        'CRS':QgsCoordinateReferenceSystem(crs1)
                        })
                        
        start_time_DTM = time.time()
        
        output_DTM = f'{output_directory}/DTM.tif'
        feedback.pushInfo("Creating DTM ...")
        processing.run("pdal:exportrastertin", 
        {'INPUT':output_filter,'RESOLUTION':0.5,'TILE_SIZE':1000,'FILTER_EXPRESSION':'','FILTER_EXTENT':None,'ORIGIN_X':None,
        'ORIGIN_Y':None,'OUTPUT':output_DTM})
                
        elapsed_time_DTM = time.time() - start_time_DTM  # Measure elapsed time for step 1
        feedback.pushInfo(f"Time elapsed for creating DTM: {format_time(elapsed_time_DTM)}")

                               
    #################################################### Line (river) editing#################################################
        start_time_profiles = time.time()
        
        #Clip river by las boundary
        step_1 = processing.run("native:clip",
                       {'INPUT':line_path,
                        'OVERLAY':boundary,
                        'OUTPUT':'TEMPORARY_OUTPUT'})
        
        result1 = processing.run("native:dissolve",
                                 {'INPUT': step_1['OUTPUT'],
                                  'FIELD': [],
                                  'SEPARATE_DISJOINT': False,
                                  'OUTPUT': 'TEMPORARY_OUTPUT'})
                                         
        result2 = processing.run("native:densifygeometriesgivenaninterval",
                                 {'INPUT': result1['OUTPUT'],
                                  'INTERVAL': 1, 'OUTPUT': 'TEMPORARY_OUTPUT'})

        #Creating transect (lines of profiles)
        result3 = processing.run("native:transect",
                                 {'INPUT': result2['OUTPUT'],
                                  'LENGTH': Width, 'ANGLE': 90, 'SIDE': 2,
                                  'OUTPUT': 'TEMPORARY_OUTPUT'})
                
        #Extraction of profiles selected by user based on expression
        expr = f'"TR_ID" % {Spacing} = 0'

        result4 = processing.run("native:extractbyexpression",
                                 {'INPUT': result3['OUTPUT'],
                                  'EXPRESSION': expr,
                                  'OUTPUT': 'TEMPORARY_OUTPUT'})
        
        output_profile = f'{output_directory}/profile.shp'
        output_profiles = f'{output_directory}/profiles.shp'
        
        #creating profile lines
        result5 = processing.run("sagang:profilesfromlines",
                                 {'DEM': output_DTM,
                                  'VALUES': None,
                                  'LINES': result4['OUTPUT'],  
                                  'NAME': 'ID',
                                  'PROFILE': output_profile,
                                  'PROFILES': output_profiles, 'SPLIT': False})
        
        attribute_layer = QgsVectorLayer(output_profile, "profile", "ogr")
        fields = attribute_layer.fields()
        field_name = fields[0].name()
      
        
        #Profile layer for preview
        output_Profile_layer = f'{output_directory}/Profile_layer.shp'
        result6 = processing.run("native:joinattributesbylocation",
                                 {'INPUT': result4['OUTPUT'], 'PREDICATE': [0],
                                  'JOIN': output_profile,
                                  'JOIN_FIELDS': field_name, 'METHOD': 0,
                                  'DISCARD_NONMATCHING': True, 'PREFIX': '', 'OUTPUT': output_Profile_layer})
  
        #deleting temporary (unnecessary) files
        files_to_remove = []
        files_to_remove.extend(glob.glob(os.path.join(output_directory, "profiles_01.*")))
        files_to_remove.extend(glob.glob(os.path.join(output_directory, "extracted_boundary.*")))
       
        for file_path in files_to_remove:
            os.remove(file_path)
           
        elapsed_time_profiles = time.time() - start_time_profiles  # Measure elapsed time for step 1
        feedback.pushInfo(f"Time elapsed for creating profiles: {format_time(elapsed_time_profiles)}")
        ####################################################Graph#################################################                                  
        start_time_graphs= time.time()
        gdf = gpd.read_file(os.path.join(output_directory, 'profile.shp'))

        for id_line, group in gdf.groupby(field_name):
            x_data = []
            y_data = []

            for idx, row in group.iterrows():
                # Check for the desired field name and assign the value to x_value
                if 'DIST' in row:
                    x_value = row['DIST']
                elif 'DISTANCE' in row:
                    x_value = row['DISTANCE']
                else:
                    feedback.pushInfo(f"{output_profile_final} was not correctly generated")
                y_value = row['Z']


                x_data.append(x_value)
                y_data.append(y_value)

            plt.figure(figsize=(20, 6))
            min_y = min(y_data)
            max_y = max(y_data)
            y_Spacing = max_y - min_y
            step_size = y_Spacing / 10  # intervals for axis Y

            yticks = [round(min_y + i * step_size, 2) for i in range(int(y_Spacing / step_size) + 1)]
            plt.yticks(yticks)
            min_x = min(x_data)
            max_x = max(x_data)
            x_Spacing = max_x - min_x
            step_size_x = x_Spacing / 10  # intervals for axis X

            xticks = [round(min_x + i * step_size_x, 2) for i in range(int(x_Spacing / step_size_x) + 1)]
            xticks_labels = [f'{x / 10:.2f}' for x in xticks]  # dist/100

            plt.grid(color='gray', linestyle='-', linewidth=0.1)

            output_path = os.path.join(output_directory, f'profile_{id_line}.png')
            feedback.pushInfo(f"Saving profile {id_line} to {output_path}")

            # style
            plt.plot(x_data, y_data, linestyle='-', color='blue', linewidth=.5, label='graph')
            plt.xlabel('distance [m]')
            plt.ylabel('elevation [m]')
            plt.title(f'Cross-section profile {id_line}')

            plt.savefig(output_path)
            plt.close()  # Close the figure after saving
            
        elapsed_time_graphs = time.time() - start_time_graphs  # Measure elapsed time creating graphs
        feedback.pushInfo(f"Time elapsed for creating graphs: {format_time(elapsed_time_graphs)}")
        
        ############################# preview ############################################################

        DTM_layer = QgsRasterLayer(output_DTM, 'DTM')
        profile_layer = QgsVectorLayer(output_Profile_layer, 'Profile_layer', 'ogr')

        #Adding_layers
        QgsProject.instance().addMapLayer(DTM_layer)
        QgsProject.instance().addMapLayer(profile_layer)

        # Access the layout manager
        manager = QgsProject.instance().layoutManager()
        layoutName = 'Layout'
        layouts_list = manager.layouts()
        
        # Remove any duplicate layouts
        for layout in layouts_list:
            if layout.name() == layoutName:
                manager.removeLayout(layout)
                
        # Specify the layout name
        layout = QgsPrintLayout(QgsProject.instance())
        layout.initializeDefaults()
        layout.setName(layoutName)
        manager.addLayout(layout)
        
        # Create map item in layout
        map = QgsLayoutItemMap(layout)
        map.setRect(20, 20, 20, 20)

        # Set map extent
        rect = QgsRectangle(DTM_layer.extent())
        map.setExtent(rect)

        # Resize and zoom the map item
        map.attemptMove(QgsLayoutPoint(5, 20, QgsUnitTypes.LayoutMillimeters))
        map.attemptResize(QgsLayoutSize(285, 185, QgsUnitTypes.LayoutMillimeters))
        map.zoomToExtent(DTM_layer.extent())

        # Add the map item to the layout
        layout.addLayoutItem(map)
        
        #style for line feature
        symbol = QgsLineSymbol.createSimple({'color': 'red', 'width': '0.2'})
        renderer = QgsSingleSymbolRenderer(symbol)
        profile_layer.setRenderer(renderer)
        profile_layer.triggerRepaint()
        
        # Adding title
        title = QgsLayoutItemLabel(layout)
        title_text_format = QgsTextFormat()
        title_text_format.setSize(20)
        title.setTextFormat(title_text_format)
        title.setText("Preview of the profiles ")
        title.adjustSizeToText()
        layout.addLayoutItem(title)
        title.attemptMove(QgsLayoutPoint(100, 5, QgsUnitTypes.LayoutMillimeters))
        
        # Adding labels
        label_settings = QgsPalLayerSettings()
        label_settings.fieldName = field_name
        label_settings.enabled = True
        label_settings.placement = QgsPalLayerSettings.Line
        label_settings.overrunDistance=(2)
        
        # text format
        text_format = QgsTextFormat()
        text_format.setSize(7)
        
        # Buffer (labels)
        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setColor(QColor(255, 255, 255))
        buffer_settings.setSize(0.5)
        text_format.setBuffer(buffer_settings)
        label_settings.setFormat(text_format)
        labeler = QgsVectorLayerSimpleLabeling(label_settings)
        profile_layer.setLabelsEnabled(True)
        profile_layer.setLabeling(labeler)
        profile_layer.triggerRepaint()

        #export preview
        layout = manager.layoutByName(layoutName)
        exporter = QgsLayoutExporter(layout)
        feedback.pushInfo(f"Saving preview to {os.path.join(output_directory, 'preview.png')}")
        preview = os.path.join(output_directory, 'preview.png')
        exporter.exportToImage(preview, QgsLayoutExporter.ImageExportSettings())
              
        return {}

    def name(self):
        return 'cross_profiles'

    def tr(self, string):
        return QCoreApplication.translate('cross_profiles', string)

    def displayName(self):
        return self.tr('Cross Profiles')

    def group(self):
        return self.tr('')

    def groupId(self):
        return ''
        
    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("Cross profiles is a QGIS tool designed for creating cross-sectional profile graphs from LiDAR data.\
        It integrates LAS files and vector lines, to generate cross-sectional profiles at specified intervals.\
        It exports these profiles as PNG image files and displays them alongside a terrain map preview.\n\
        <b>Note:<b>\n\
        Before running the tool, make sure you have installed the matplotlib and geopandas libraries on your PC.\
        Also, ensure that you have installed the LAStools plugin, which is necessary to run this tool.\n\
        Ensure your data and environment are set to metric coordinates. Using other systems may cause errors.\n\
        Be aware that profiles around the edge of the area may be shorter than the specified length.\n\
        The processing time may variably depend on the performance of the computer and the amount of data used.\
        Processing larger amounts of data may take longer and require more disk space.\
        It is recommended to have sufficient free disk space and expect longer processing times with large data files.\n")


    def createInstance(self):
        return CrossProfilesAlgorithm()
