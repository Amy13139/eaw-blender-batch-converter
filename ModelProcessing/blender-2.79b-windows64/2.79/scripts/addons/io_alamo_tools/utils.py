import bpy
import struct
import mathutils


# utilities


def find_armature():
	armature_name = bpy.context.scene.ActiveSkeleton.skeletonEnum
	if armature_name == 'None':
		return None
	armature = bpy.data.objects[armature_name]
	return armature


def get_current_action():
	arm = find_armature()
	if arm is not None:
		if arm.animation_data is not None and arm.animation_data.action is not None:
			return arm.animation_data.action
		else:
			return None
	else:
		return None


def clean_name(name):
	# remove Blenders numbers at the end of names
	if name[len(name) - 4:len(name) - 3] == ".":
		cut = name[0:len(name) - 4]
		return cut
	else:
		return name


def set_mode_object():
	if bpy.context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode='OBJECT')


def set_mode_edit():
	if bpy.context.mode != 'EDIT':
		bpy.ops.object.mode_set(mode='EDIT')


# pack


def pack_int(input_int):
	return struct.pack("<I", input_int)


def pack_float(input_float):
	return struct.pack("<f", input_float)


def pack_u_char(input_char):
	return struct.pack("<B", input_char)


def pack_char(input_char):
	return struct.pack("<b", input_char)


def pack_short(input_short):
	return struct.pack("<h", input_short)


def pack_u_short(input_short):
	return struct.pack("<H", input_short)


# unpack

def read_chunk_length(input_file):
	# the height bit is used to tell if chunk holds data or chunks, so if it is set it has to be ignored when
	# calculating length
	length = read_int(input_file.read(4))
	if length >= 2147483648:
		length -= 2147483648
	return length


def read_u_short(input_short):
	return struct.unpack("<H", input_short)[0]


def read_short(input_short):
	return struct.unpack("<h", input_short)[0]


def read_float(input_float):
	return struct.unpack("<f", input_float)[0]


def read_int(input_int):
	return struct.unpack("<I", input_int)[0]


def read_long(input_long):
	return struct.unpack("l", input_long)[0]


def even(n):
	if n % 2 == 0:
		return True
	else:
		return False
