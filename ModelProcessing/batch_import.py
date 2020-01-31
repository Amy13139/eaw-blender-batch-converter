from sys import stdout, stdin
import subprocess
import shlex
from sys import argv
from os import path, listdir, remove, getcwd


def cushion(string):
	return '"' + string + '"'


# Blender Exe Path, Save directory, and command line arguments
blender_dir = path.join(getcwd(), 'blender-2.79b-windows64\\')
import_script = cushion(path.join(blender_dir, 'import_file.py'))  # Cushion with parentheses
save_dir = path.join(blender_dir, 'Blend_ALO_Files')
blender_file = cushion(path.join(blender_dir, 'blender.exe'))  # Cushion with parentheses
blender_args = shlex.split(blender_file + ' -b --python-exit-code 0 -P ' + import_script)

# Variables to replace with stdin reads when attached to larger program
import_dir = argv[1]  # stdin.readline().strip()
animation_dir = argv[2]  # stdin.readline().strip()
# log_dir = stdin.readline().strip()

if import_dir == '':
	raise Exception("Import Directory parameter cannot be blank")

# Log and Stream Variables
log_path = path.join(blender_dir, 'log.txt')
exclude_path = path.join(blender_dir, 'exclude.txt')


def make_file(file_path, wipe=True):
	if wipe or not path.isfile(file_path):
		file = open(file_path, 'w')
		file.close()


def make_input(input_dict):
	input_string = ''
	for item in (path.join(import_dir, file_name), save_dir, animation_dir, blender_dir):
		input_string += item + "\n"
	input_dict.update({'input': input_string})


# Regen/Open files
# make_file(log_path)
make_file(exclude_path)

# Arguments for subprocess.run() when called on blender, input should be set to (import_file+'\n'+save_dir)
subprocess_args = {'stdout': stdout, 'stderr': subprocess.STDOUT, 'universal_newlines': True, 'input': ''}

# Clear Old Saved Files
for old in listdir(save_dir):
	remove(path.join(save_dir, old))

# Get Dir List
dir_list = listdir(import_dir)

# iterate over models
for index, file_name in enumerate(dir_list):
	# Check if input_file is an ALO
	if file_name.lower().endswith(".alo"):
		# Check txt of exclusions
		with open(exclude_path, 'rt') as exclude_txt:
			if file_name in exclude_txt.read().split('\n'):
				print("\n" + file_name + " present in exclusions.txt, skipping")
				continue

		# Set Input to newline sep import_file,save_dir,animation_dir
		make_input(subprocess_args)

		# Run Blender
		print("\n\nImporting: " + file_name)
		returned_streams = subprocess.run(blender_args, **subprocess_args)
		# sys.stdin.readline().strip() in opened process for 1 input line
		print("Blender Process Completed")
