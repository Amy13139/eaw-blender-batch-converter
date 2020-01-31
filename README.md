# EaW-Blender-Batch-Converter
This is a simple python script that utilizes a modified version of Gaulker's Alamo Tools for Blender to convert an entire directory of .ALO files into .BLEND files. Includes functionality to import sub-models and animations based on matching filenames.

# Using the Converter
To use, launch the batch_import.py script from the command line with arguments for both a model directory and an animation directory. All animations must be in V2 .ALA format (See [modtools.petrolution.net](modtools.petrolution.net) for info and a conversion program). Any files that are not in their proper directory will be ignored. Made with Python 3.8. Leave animation path empty ("") to disable animation imports.

Example scripts:
python batch_import.py "C:\path\to\eaw\models" "C:\path\to\eaw\converted_animations"
python3 "C:\blender\batch_import.py" "C:\path\to\eaw\models" "C:\path\to\eaw\models\converted_animations"
python3 "C:\blender\batch_import.py" "C:\path\to\eaw\models" ""

NOTE: If you are converting models from Star Wars: Empire at War: Forces of Corruption, please rename the "EV_Stardestoyer_Thrawn.Alo" file to "EV_Stardestroyer_Thrawn.Alo". Also, consider removing some of the Stormtrooper variants or disable importing of sub-models for them, alongside other problematic files. 

# Advanced Settings
Since I have moved on from working on this project, there is no user-friendly way to toggle settings. I tried to organize Gaulker's code as best I could, but it can still be messy to navigate. Most options can be toggled by settings values in the body of the execute() function in import_alo.py. Any changes that are not directly tied to a controlling varible will require Python knowledge to impliment, but I have commented most of the code I changed to help facilitate edits.
