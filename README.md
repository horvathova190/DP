This tool is based on Master's thesis: Creating of River Cross Profiles from Lidar Data. It integrates LAS files and vector files containing river data (line features) to generate 
cross-sectional profiles at specified intervals. These profiles are exported as PNG image files and displayed alongside a terrain map preview. 
It's  designed for QGIS (3.32 and later). You need plugins to run it - Sagang and Lastools. 
Outputs of this tool are multiple and all of them will save to folder of your choice. These outputs are - merged (only if you have multiple files in folder) and filtered point cloud,
digital terrain model, two sets of profile layers, profile graphs and map preview. 

Useful lines in the script:

  line 165 - if you want to change value for filtering point cloud, change value in parameter - 'FILTER_EXPRESSION':'Classification = Classification_value_by_your_choice'; 
                                                                                                for example: 'FILTER_EXPRESSION': Classification = 2

  line 192 - if you want to change the DMT resolution, change value of this paramter by your choice: 'RESOLUTION': 'resolution'


You can see a test run of the tool in this video:
https://www.youtube.com/watch?v=8gFUryUv0dw 

If you have any questions, or problems with running this script, contact me on horvathova190@uniba.sk
