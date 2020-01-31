import bpy
from .utils import *
from bpy.props import (StringProperty,
					BoolProperty,
					FloatProperty,
					EnumProperty)
import mathutils
import math
from bpy.props import *
import sys
import os
import bmesh
import binascii


class AnimationData:
	def __init__(self):
		self.num_frames = 0
		self.fps = 0
		self.num_bones = 0

		self.bone_name_list = []
		self.bone_index = []

		self.translation_offset = []
		self.translation_index = []
		self.translation_data = []
		self.translation_block_size = 0
		self.translation_scale = []

		self.scale_block_size = 0
		self.scale_index = []
		self.scale_offset = []
		self.scale_scale = []

		self.rotation_index = []
		self.default_rotation = []
		self.rotation_block_size = 0
		self.rotation_data = []

		self.visibility_animation = []
		self.visibility_dict = {}


def read_visibility_data(data, bone_name):
	length = read_chunk_length(input_file)
	if length * 8 < data.num_frames:
		raise Exception("Error reading lengths in input_file")

	visibility = []
	vis_byte = b''

	# (vis_byte[F / 8] >> (F % 8)) & 1, F = frame number
	for current_frame in range(data.num_frames):
		if not current_frame % 8:
			vis_byte = input_file.read(1)[::-1].zfill(8)  # Get byte, reverse it because little endian, then zero-pad 
		# to be a full byte 
		is_visible = bool(vis_byte[current_frame % 8])
		visibility.append(is_visible)

	if bone_name in data.visibility_dict:
		bone_name += ".001"
		counter = 2
		while bone_name in visibility_dict:
			if counter < 10:
				bone_name = bone_name[0:len(bone_name) - 4] + ".00" + str(counter)
			elif counter < 100:
				bone_name = bone_name[0:len(bone_name) - 4] + ".0" + str(counter)
			else:
				bone_name = bone_name[0:len(bone_name) - 4] + "." + str(counter)
			counter += 1
	data.visibility_dict[bone_name] = visibility


def read_translation_data(data):
	if data.num_frames == 0 or data.translation_block_size == 0:
		print(data.num_frames)
		raise Exception("Neither num_frames nor block size can be 0")

	v = mathutils.Vector()
	for frame in range(data.num_frames):
		translations = []
		for item in range(data.translation_block_size + 1):
			if (item % 3 == 0) and (item != 0):
				translations.append(v)
				v = mathutils.Vector()
				if item == data.translation_block_size:
					break
			v[item % 3] = utils.read_u_short(input_file.read(2))
		data.translation_data.append(translations)


def read_rotation_data(data):
	# num_words = data.num_frames * data.rotation_block_size
	if data.num_frames == 0 or data.rotation_block_size == 0:
		print(data.num_frames)
		raise Exception("Neither num frames nor block size can be 0")

	q = mathutils.Quaternion()
	for frame in range(data.num_frames):
		rotations = []
		for item in range(data.rotation_block_size + 1):
			if (item % 4 == 0) and (item != 0):
				rotations.append(q)
				q = mathutils.Quaternion()
				if item == data.rotation_block_size:
					break
			q[(item + 1) % 4] = utils.read_short(input_file.read(2)) / 32767
		data.rotation_data.append(rotations)


def read_next_chunk(path):
	def skip_chunk():
		skip_length = read_chunk_length(input_file)
		input_file.seek(skip_length, 1)

	data = AnimationData()
	skip_chunk_indicators = [b"\x08\x10\x00\x00", b"\x0B\x10\x00\x00"]
	while input_file.tell() < os.path.getsize(path):
		active_chunk = input_file.read(4)

		if active_chunk == b"\x00\x10\x00\x00":
			input_file.seek(4, 1)  # skip size

		elif active_chunk == b"\x01\x10\x00\x00":
			if utils.read_int(input_file.read(4)) != 36:
				return 'WRONG_FORMAT'
			read_animation_information(data)

		elif active_chunk == b"\x02\x10\x00\x00":
			input_file.seek(4, 1)  # skip size

		elif active_chunk == b"\x03\x10\x00\x00":
			chunk_length = read_chunk_length(input_file)
			end_position = input_file.tell() + chunk_length
			read_bone_animation_info(data, end_position)

		elif active_chunk == b"\x0A\x10\x00\x00":
			if data.translation_block_size:
				input_file.seek(4, 1)  # skip size
				read_translation_data(data)
			else:
				chunk_length = read_chunk_length(input_file)
				input_file.seek(chunk_length, 1)

		elif active_chunk == b"\x09\x10\x00\x00":
			if data.rotation_block_size:
				input_file.seek(4, 1)  # skip size
				read_rotation_data(data)
			else:
				chunk_length = read_chunk_length(input_file)
				input_file.seek(chunk_length, 1)

		elif active_chunk in skip_chunk_indicators:
			skip_chunk()

	return data


def read_animation_information(data):
	input_file.seek(2, 1)  # skip mini chunk and size
	data.num_frames = utils.read_int(input_file.read(4))

	input_file.seek(2, 1)  # skip mini chunk and size
	data.fps = utils.read_float(input_file.read(4))

	input_file.seek(2, 1)  # skip mini chunk and size
	data.num_bones = utils.read_int(input_file.read(4))

	input_file.seek(2, 1)  # skip mini chunk and size
	data.rotation_block_size = utils.read_int(input_file.read(4))

	input_file.seek(2, 1)  # skip mini chunk and size
	data.translation_block_size = utils.read_int(input_file.read(4))

	input_file.seek(2, 1)  # skip mini chunk and size
	data.scale_block_size = utils.read_int(input_file.read(4))

	# Checks on data sizes
	if not data.num_frames and not data.num_bones:
		raise Exception("Frame/Bone number data read incorrectly, cannot be 0")
	if data.translation_block_size % 3:
		raise Exception("Translation data read incorrectly, cannot construct vectors")
	if data.rotation_block_size % 4:
		raise Exception("Rotation data read incorrectly, cannot construct quaternions")


def read_bone_name(data):
	length = int.from_bytes(input_file.read(1), byteorder='little')  # get string length
	bone_name = ""
	for char in range(length - 1):
		letter = input_file.read(1).decode(encoding="ASCII")
		bone_name += letter

	input_file.seek(1, 1)  # skip end byte of name
	if bone_name in data.visibility_dict:
		bone_name += ".001"
		counter = 2
		while bone_name in data.visibility_dict:
			if counter < 10:
				bone_name = bone_name[0:len(bone_name) - 4] + ".00" + str(counter)
			elif counter < 100:
				bone_name = bone_name[0:len(bone_name) - 4] + ".0" + str(counter)
			else:
				bone_name = bone_name[0:len(bone_name) - 4] + "." + str(counter)
			counter += 1

	return bone_name


def read_bone_animation_info(data, end_position):
	def read_mini_chunk_length(input_file):
		return utils.read_int(input_file.read(1) + bytearray(3))

	while input_file.tell() < end_position:
		active_child_chunk = input_file.read(1)
		if active_child_chunk == b"\x04":
			bone_name = read_bone_name(data)
			data.bone_name_list.append(bone_name)

		elif active_child_chunk == b"\x05":
			length = read_mini_chunk_length(input_file)  # skip mini chunk size
			if length == 4:
				index = utils.read_int(input_file.read(4))
			if length == 2:
				index = utils.read_short(input_file.read(2))
			data.bone_index.append(index)

		elif active_child_chunk == b"\x06":
			input_file.seek(1, 1)  # skip mini chunk size
			vector = mathutils.Vector((0, 0, 0))
			vector[0] = utils.read_float(input_file.read(4))
			vector[1] = utils.read_float(input_file.read(4))
			vector[2] = utils.read_float(input_file.read(4))
			data.translation_offset.append(vector)

		elif active_child_chunk == b"\x07":
			input_file.seek(1, 1)  # skip mini chunk size
			vector = mathutils.Vector((0, 0, 0))
			vector[0] = utils.read_float(input_file.read(4))
			vector[1] = utils.read_float(input_file.read(4))
			vector[2] = utils.read_float(input_file.read(4))
			data.translation_scale.append(vector)

		elif active_child_chunk == b'\x08':
			input_file.seek(1, 1)  # skip mini chunk size
			scale_offset = [utils.read_float(input_file.read(4)), utils.read_float(input_file.read(4)),
							utils.read_float(input_file.read(4))]
			data.scale_offset.append(scale_offset)

		elif active_child_chunk == b'\x09':
			input_file.seek(1, 1)  # skip mini chunk size
			scale_scale = [utils.read_float(input_file.read(4)), utils.read_float(input_file.read(4)),
						utils.read_float(input_file.read(4))]
			data.scale_scale.append(scale_scale)

		elif active_child_chunk == b'\x0A':  # 10
			length = read_mini_chunk_length(input_file)  # skip mini chunk size and dword, unknown purpose
			input_file.seek(length, 1)

		elif active_child_chunk == b"\x0E":  # 14
			length = read_mini_chunk_length(input_file)  # skip mini chunk size
			if length == 4:
				index = utils.read_int(input_file.read(4))
			elif length == 2:
				index = utils.read_short(input_file.read(2))
			data.translation_index.append(index)

		elif active_child_chunk == b"\x0F":  # 15
			length = read_mini_chunk_length(input_file)  # skip mini chunk size
			if length == 4:
				index = utils.read_int(input_file.read(4))
			elif length == 2:
				index = utils.read_short(input_file.read(2))
			data.scale_index.append(index)

		elif active_child_chunk == b"\x10":  # 16
			length = read_mini_chunk_length(input_file)  # skip mini chunk size
			if length == 4:
				index = utils.read_int(input_file.read(4))
			elif length == 2:
				index = utils.read_short(input_file.read(2))
			data.rotation_index.append(index)

		elif active_child_chunk == b'\x11':  # 17
			input_file.seek(1, 1)  # skip mini chunk size
			q = mathutils.Quaternion()
			q[1] = read_short(input_file.read(2))
			q[2] = read_short(input_file.read(2))
			q[3] = read_short(input_file.read(2))
			q[0] = read_short(input_file.read(2))

			for i in range(4):
				q[i] = q[i] / 32767.0

			data.default_rotation.append(q)

	if 'bone_name' not in locals():
		raise Exception("Animation data read incorrectly, no name set")

	chunk = input_file.read(4)
	if chunk == b"\x07\x10\x00\x00":
		read_visibility_data(data, bone_name)
	else:
		input_file.seek(-4, 1)


def create_animation(data):
	def unpack_rotation():
		# unpack data
		if data.rotation_block_size:
			if data.rotation_index[bone_counter] != -1:
				index = int(data.rotation_index[bone_counter] / 4)  # /4, since quarantines

				frame_list = data.rotation_data[fps_counter]
				return frame_list[index]

		return data.default_rotation[bone_counter]

	def unpack_translation():
		offset = data.translation_offset[bone_counter]
		if data.translation_block_size:
			if data.translation_index[bone_counter] != -1:
				scale = data.translation_scale[bone_counter]
				index = int(data.translation_index[bone_counter] / 3)  # /3, since 3d vectors
				t_packed = data.translation_data[fps_counter]
				t_packed = t_packed[index]
				for i in range(3):
					t_packed[i] = t_packed[i] * scale[i]
				return offset + t_packed

		return offset

	action = utils.get_current_action()
	action.AnimationEndFrame = data.num_frames - 1
	action.use_fake_user = True

	scene = bpy.context.scene
	scene.frame_start = 0

	tmp_max_frames = scene.frame_end
	tmp_fps = scene.render.fps

	scene.frame_end = data.num_frames - 1
	scene.render.fps = data.fps
	scene.frame_set(0)

	utils.set_mode_object()

	armature = utils.find_armature()
	armature.select = True  # select the skeleton
	bpy.context.scene.objects.active = armature

	bpy.ops.object.mode_set(mode='POSE')  # enter pose mode

	bpy.ops.pose.rot_clear()
	bpy.ops.pose.scale_clear()
	bpy.ops.pose.transforms_clear()

	fps_counter = 0  # initialize fps_counter, corresponds to current animation frame

	while fps_counter < data.num_frames:
		bone_counter = 0

		while bone_counter < data.num_bones:

			# Unpack data + Get matrices
			rotation_unpacked = unpack_rotation()
			rotation_matrix = rotation_unpacked.to_matrix().to_4x4()

			location_unpacked = unpack_translation()
			translation_matrix = mathutils.Matrix.Translation(location_unpacked).to_4x4()

			if data.bone_name_list[data.bone_index[bone_counter] - 1] in armature.pose.bones:
				pose = armature.pose.bones[data.bone_name_list[bone_counter]]  # pose bone of current bone
				bone = armature.data.bones[data.bone_name_list[bone_counter]]  # bone of current bone

				if pose.parent is not None:
					pose.matrix = pose.parent.matrix * translation_matrix * rotation_matrix
				else:
					pose.matrix = translation_matrix * rotation_matrix

				if data.rotation_index[bone_counter] != -1 or fps_counter == 0 or fps_counter == data.num_frames - 1:
					pose.keyframe_insert(data_path='rotation_quaternion')

				if data.translation_index[bone_counter] != -1:
					pose.keyframe_insert(data_path='location')

				if bone.name in data.visibility_dict:
					pose.proxyIsHiddenAnimation = not data.visibility_dict[pose.name][fps_counter]
					pose.keyframe_insert(data_path='proxyIsHiddenAnimation')

			bone_counter += 1

		fps_counter += 1
		scene.frame_set(scene.frame_current + 1)

	# reset frames
	scene.frame_set(0)

	if scene.frame_end < tmp_max_frames:
		scene.frame_end = tmp_max_frames
	if scene.render.fps < tmp_fps:
		scene.render.fps = tmp_fps


def validate(data):
	armature = utils.find_armature()
	for name in data.bone_name_list:
		if name not in armature.data.bones:
			print("Error: Animation Bones Do Not Match Active Armature")
			print("Bone: " + name)
			return False
	if data.rotation_block_size:
		for rot_frame in data.rotation_data:
			if len(rot_frame) != data.rotation_block_size / 4:
				print("Error: Actual rotation block sizes do not match expected frame block sizes")
				print("Expected: " + str(len(rot_frame)) + "==" + str(data.rotation_block_size / 4))
				return False
	if data.translation_block_size:
		for trans_frame in data.translation_data:
			if len(trans_frame) != data.translation_block_size / 3:
				print("Error: Actual transform block sizes do not match expected frame block sizes")
				print("Expected: " + str(len(trans_frame)) + "==" + str(data.translation_block_size / 3))
				return False
	if len(data.rotation_index) != data.num_bones:
		print("Error: Actual rotation block index does not match bone number")
		print("Expected: " + str(len(data.rotation_index)) + "==" + str(data.num_bones))
		return False
	if len(data.translation_index) != data.num_bones:
		print("Error: Actual translation block index does not match bone number")
		print("Expected: " + str(len(data.translation_index)) + "==" + str(data.num_bones))
		return False

	return True


class AnimationImporter:
	@staticmethod
	def load_animation(filepath):
		global file
		file = open(filepath, 'rb')  # 'rb' - open for reading in binary mode
		data = read_next_chunk(filepath)
		if data == 'WRONG_FORMAT':
			raise Exception("Error: Wrong animation format for " + os.path.basename(filepath))
		if validate(data):

			filepath = filepath[0:-4]
			file_name_index = filepath.rfind("\\") + 1
			file_name = filepath[file_name_index:]

			model_name = bpy.context.scene.modelFileName  # doesn't always match

			if model_name != "":
				if model_name == file_name[:len(model_name)]:
					file_name = file_name[len(model_name) + 1:]

			action = bpy.data.actions.new("")
			action.name = file_name

			arm = utils.find_armature()

			if not arm.animation_data:
				arm.animation_data_create()
			arm.animation_data.action = action

			create_animation(data)


# noinspection PyUnusedLocal
class AlaImporter(bpy.types.Operator):
	"""ALA Importer"""  # blender will use this as a tooltip for menu items and buttons.
	bl_idname = "import.ala"  # unique identifier for buttons and menu items to reference.
	bl_label = "Import ALA File"  # display name in the interface.
	bl_options = {'REGISTER', 'UNDO'}  # enable undo for the operator.
	filename_ext = ".ala"
	filter_glob = StringProperty(default="*.ala", options={'HIDDEN'})
	bl_info = {
		"name": "ALA Importer",
		"category": "Import"}

	filepath = StringProperty(name="File Path", description="Filepath used for importing the ALA input_file",
							maxlen=1024, default="")

	def execute(self, context):  # execute() is called by blender when running the operator.

		importer = AnimationImporter()
		animation_path = self.properties.filepath
		importer.load_animation(animation_path)
		utils.set_mode_object()
		return {'FINISHED'}  # this lets blender know the operator finished successfully.

	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}
