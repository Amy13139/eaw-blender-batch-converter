import bpy
from . import settings, utils, import_ala
from .utils import *
from .settings import *

from bpy.props import (StringProperty,
					BoolProperty,
					IntProperty,
					FloatProperty,
					EnumProperty,
					PointerProperty)
from bpy.types import Panel, Operator, PropertyGroup
import struct
import mathutils
import math
from math import pi
from mathutils import Vector
from bpy.props import *
from bpy_extras.io_utils import ExportHelper, ImportHelper
import sys
import os
from os import listdir
import bmesh


# noinspection PyGlobalUndefined,PyUnusedLocal,PyRedeclaration
class AloImporter(bpy.types.Operator):
	"""ALO Importer"""  # blender will use this as a tooltip for menu items and buttons.
	bl_idname = "wm.alo"  # unique identifier for buttons and menu items to reference.
	bl_label = "Import ALO File"  # display name in the interface.
	bl_options = {'REGISTER'}  # do not undo for the operator.
	filename_ext = ".alo"
	filter_glob = StringProperty(default="*.alo", options={'HIDDEN'})
	bl_info = {
		"name": "ALO Importer",
		"category": "Import"
	}

	importAnimations = BoolProperty(
		name="Import Animations",
		description="Import the model's animations from the same path",
		default=True)  # Change to false to disable auto-animation import

	global material_props
	material_props = ["BaseTexture", "NormalTexture", "GlossTexture", "WaveTexture", "DistortionTexture",
					"CloudTexture",
					"CloudNormalTexture", "Emissive", "Diffuse", "Specular", "Shininess", "Colorization",
					"DebugColor",
					"UVOffset", "Color", "UVScrollRate", "DiffuseColor", "EdgeBrightness", "BaseUVScale",
					"WaveUVScale",
					"DistortUVScale", "BaseUVScrollRate", "WaveUVScrollRate", "DistortUVScrollRate", "BendScale",
					"Diffuse1", "CloudScrollRate", "CloudScale", "SFreq", "TFreq", "DistortionScale", "Atmosphere",
					"CityColor", "AtmospherePower"]

	global billboard_mode_array
	billboard_mode_array = ["Disable", "Parallel", "Face", "ZAxis View", "ZAxis Light", "ZAxis Wind",
							"Sunlight Glow", "Sun"]

	def draw(self, context):
		layout = self.layout
		layout.prop(self, "importAnimations")

	file_path = StringProperty(name="File Path", description="Filepath used for importing the ALO input_file",
							maxlen=1024,
							default="")
	file_name = StringProperty(name="File Name", description="Filename used for importing the ALO input_file",
							maxlen=1024,
							default="")
	save_dir = StringProperty(name="Save Dir", description="Path used for saving the ALO input_file as a blend",
							maxlen=1024,
							default="")

	def update_path(self, filepath):
		self.properties.file_path = filepath
		self.properties.file_name = os.path.basename(filepath)

	# noinspection PyBroadException, PyUnusedLocal
	def execute(self, context):  # execute() is called by blender when running the operator.

		# main structures, called directly from execute

		def import_model():
			global armatureData, o_meshNameList

			def create_armature():

				def get_bone_count(input_armature_data):
					file.seek(8, 1)  # skip header and proxy_chunk_size
					bone_count = utils.read_int(file.read(4))
					input_armature_data.boneCount = bone_count
					file.seek(124, 1)  # skip padding

				def process_bone(input_armature_data):
					new_bone = Bone()
					input_armature_data.bones.append(new_bone)

					file.seek(12, 1)  # skip header and proxy_chunk_size and next header
					new_bone.name = cut_string(read_string())
					bone_type = file.read(4)
					if bone_type == b"\x05\x02\x00\00":  # Check new_bone version
						has_billboard = False
					elif bone_type == b"\x06\x02\x00\00":
						has_billboard = True
					file.seek(4, 1)  # skip proxy_chunk_size
					new_bone.parentIndex = read_int(file.read(4))
					if new_bone.name == 'Root':
						new_bone.parentIndex = 0
					new_bone.visible = read_int(file.read(4))
					if has_billboard:
						new_bone.billboard = read_int(file.read(4))
					else:
						new_bone.billboard = 0  # Assume zero if BoneV1 (No billboard field)

					def make_matrix_row(input_file):
						return read_float(input_file.read(4)), read_float(input_file.read(4)), read_float(input_file.read(4)), \
							read_float(input_file.read(4))

					new_bone.matrix = (make_matrix_row(file), make_matrix_row(file), make_matrix_row(file), (0, 0, 0, 1))

				def create_bone(bone_data, input_armature_blender, input_armature_data):

					new_bone = input_armature_blender.edit_bones.new(bone_data.name)
					new_bone.tail = mathutils.Vector([0, 1, 0])

					if bone_data.visible == 1:
						new_bone.Visible = True
					else:
						new_bone.Visible = False

					parent = input_armature_data.bones[bone_data.parentIndex].name
					if parent != 'Root':
						new_bone.parent = input_armature_blender.edit_bones[parent]
						new_bone.matrix = new_bone.parent.matrix * mathutils.Matrix(bone_data.matrix)
					else:
						new_bone.matrix = mathutils.Matrix(bone_data.matrix)

					new_bone.billboardMode.billboardMode = billboard_mode_array[bone_data.billboard]

					bpy.ops.object.mode_set(mode='EDIT')

				bpy.ops.object.add(type='ARMATURE', enter_editmode=True, )
				armature_obj = bpy.context.object
				armature_obj.show_x_ray = True

				name = file.name.split("\\")
				name = name[-1]
				name = name[:-4]
				armature_obj.name = name + "Rig"

				armature_blender = armature_obj.data
				armature_blender.name = name + 'Armature'
				armature_blender.draw_type = 'STICK'

				armature_data = Armature()

				file.seek(4, 1)  # skip proxy_chunk_size
				get_bone_count(armature_data)

				for bone in range(armature_data.boneCount):
					process_bone(armature_data)

				for bone in armature_data.bones:
					create_bone(bone, armature_blender, armature_data)

				bpy.ops.object.mode_set(mode='OBJECT')

				bpy.context.scene.ActiveSkeleton.skeletonEnum = armature_obj.name

				return armature_data

			def get_n_objects_n_proxies():
				proxy_chunk_size = read_chunk_length(file)
				file.seek(2, 1)
				num_objects = read_long(file.read(4))
				file.seek(2, 1)
				num_proxies = read_long(file.read(4))
				num_objects_proxies = {"num_objects": num_objects, "num_proxies": num_proxies}

				# some .alo formats have an additional unspecified value at this position
				# to read the rest correctly this code checks if this is the case here and skips appropriately
				proxy_chunk_size -= 12
				file.seek(proxy_chunk_size, 1)

				return num_objects_proxies

			def read_connection(input_mesh_name_list):
				file.seek(2, 1)  # skip head and proxy_chunk_size
				mesh_index = struct.unpack("I", file.read(4))[0]
				file.seek(2, 1)  # skip head and proxy_chunk_size
				bone_index = struct.unpack("I", file.read(4))[0]
				armature_blender = utils.find_armature()

				# set connection of blender_object to new_bone and move blender_object to new_bone
				obj = None
				if mesh_index < len(input_mesh_name_list):  # light objects can mess this up
					obj = bpy.data.objects[input_mesh_name_list[mesh_index]]

				bone = armature_blender.data.bones[bone_index]

				if not main_model:
					no_prefix = input_mesh_name_list[mesh_index].partition('_')[2]
					for index, chk_bone in enumerate(armature_blender.data.bones):
						if chk_bone.name == no_prefix:
							if chk_bone.name + "_Bone" in armature_blender.data.bones:
								bone = armature_blender.data.bones[chk_bone.name + "_Bone"]
								break
							bone = armature_blender.data.bones[index]

				if obj is not None:
					if bone.name != 'Root':
						constraint = obj.constraints.new('CHILD_OF')
						constraint.target = armature_blender
						constraint.subtarget = bone.name

			def read_proxy():
				chunk_length = struct.unpack("I", file.read(4))[0]
				file.seek(1, 1)  # skip header
				name_length = struct.unpack("B", file.read(1))[0]
				proxy_name = ""
				counter = 0
				while counter < name_length - 1:
					letter = str(file.read(1))
					letter = letter[2:len(letter) - 1]
					proxy_name = proxy_name + letter
					counter += 1
				file.seek(3, 1)  # skip end byte of material_name, chunk mini header and proxy_chunk_size
				proxy_bone_index = read_int(file.read(4))

				proxy_is_hidden = False
				alt_decrease_stay_hidden = False
				counter = 0
				while name_length + 9 + counter < chunk_length:
					mini_chunk = file.read(1)
					file.seek(1, 1)
					if mini_chunk == b"\x07":
						if read_int(file.read(4)) == 1:
							proxy_is_hidden = True
					elif mini_chunk == b"\x08":
						if read_int(file.read(4)) == 1:
							alt_decrease_stay_hidden = True
					counter += 6

				armature_blender = utils.find_armature()

				bpy.context.scene.objects.active = armature_blender
				bpy.ops.object.mode_set(mode='EDIT')  # go to Edit mode
				bone = armature_blender.data.edit_bones[armature_blender.data.bones[proxy_bone_index].name]
				bone.EnableProxy = True
				bone.ProxyName = proxy_name
				bone.proxyIsHidden = proxy_is_hidden
				bone.altDecreaseStayHidden = alt_decrease_stay_hidden
				bpy.ops.object.mode_set(mode='OBJECT')  # go to Edit mode

			def create_light(input_mesh_name_list):
				light_type_list = ['POINT', 'SUN', 'SPOT']

				# read light's name
				name_size = read_chunk_length(file)
				lamp_name = file.read(name_size-1).decode(encoding='ASCII')
				file.seek(1, 1)

				# read light data
				file.seek(8, 1)
				light_type = read_int(file.read(4))

				lamp_data = bpy.data.lamps.new(name=lamp_name, type=light_type_list[light_type])

				lamp_data.color = (read_float(file.read(4)), read_float(file.read(4)), read_float(file.read(4)))
				lamp_data.energy = read_float(file.read(4))
				lamp_data.distance = read_float(file.read(4)) / 2
				file.seek(4, 1)
				if lamp_data.type == 'POINT':
					file.seek(8, 1)
				elif lamp_data.type == 'SUN':
					file.seek(8, 1)
				elif lamp_data.type == 'SPOT':
					lamp_data.spot_size = read_float(file.read(4))
					lamp_data.spot_blend = read_float(file.read(4)) / pi * lamp_data.spot_size
				input_mesh_name_list.append(lamp_data.name)

				bpy.ops.object.lamp_add(type=lamp_data.type)
				lamp_object = bpy.context.object
				lamp_object.data = lamp_data
				lamp_object.name = lamp_name
				set_mode_object()

			mesh_name_list = []
			# loop over ala_file until end is reached
			while file.tell() < os.path.getsize(file_path):
				active_chunk = file.read(4)
				# print(active_chunk)
				if active_chunk == b"\x00\x02\x00\00":
					if main_model:
						armatureData = create_armature()
					else:
						file.seek(read_chunk_length(file), 1)
				elif active_chunk == b"\x00\x04\x00\00":
					file.seek(4, 1)  # skip proxy_chunk_size
					mesh_name = process_mesh_chunk()
					mesh_name_list.append(mesh_name)
				elif active_chunk == b"\x00\x13\x00\00":
					# Skip size and next header
					print("WARNING: Light objects found, may cause problems")
					file.seek(8, 1)
					create_light(mesh_name_list)
				elif active_chunk == b"\x00\x06\x00\00":
					file.seek(8, 1)  # skip proxy_chunk_size and next header
					get_n_objects_n_proxies()  # may be used later, store if needed
					print('Found Connection Chunk')
				elif active_chunk == b"\x02\x06\x00\00":
					file.seek(4, 1)  # skip proxy_chunk_size
					read_connection(mesh_name_list)
				elif active_chunk == b"\x03\x06\x00\00":
					read_proxy()
				elif active_chunk == b'\x00\x09\x00\x00':
					print("Cannot Import ALO Particle Files")
					raise Exception("Cannot Import ALO Particle Files")

			if main_model:
				o_meshNameList = mesh_name_list

		def remove_shadow_doubles():
			if bpy.ops.object.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode='OBJECT')
			for blender_object in bpy.data.objects:
				if blender_object.type == 'MESH':
					shader = blender_object.material_slots[0].material.shaderList.shaderList
					if shader == 'MeshCollision.fx' or shader == 'RSkinShadowVolume.fx' or shader == 'MeshShadowVolume.fx':
						bpy.context.scene.objects.active = blender_object
						bpy.ops.object.mode_set(mode='EDIT')
						bpy.ops.mesh.select_all(action='SELECT')
						bpy.ops.mesh.remove_doubles()
						bpy.ops.object.mode_set(mode='OBJECT')

		# Classes
		# Bones and armature

		class Armature:
			def __init__(self):
				self.bones = []
				self.boneCount = 0

		class Bone:
			def __init__(self):
				self.name = ''
				self.parentIndex = 0
				self.visible = 0
				self.billboard = 0
				self.matrix = None

		# Mesh and material

		class MeshClass:
			def __init__(self):
				self.name = ''
				self.isHidden = False
				self.collision = False
				self.nMaterials = 0
				self.subMeshList = []

			def get_num_vertices(self):
				n_vertices = 0
				for subMesh in self.subMeshList:
					n_vertices += subMesh.nVertices
				return n_vertices

		class SubMeshClass:
			def __init__(self):
				self.nVertices = 0
				self.nFaces = 0
				self.shader = None
				self.vertices = []
				self.faces = []
				self.faceOffset = 0
				self.UVs = []
				self.material = None
				self.animationMapping = []
				self.boneIndex = []

		def process_mesh_chunk():

			def construct_mesh(input_current_mesh):

				def create_uv_layer(uv_name, uv_coordinates):
					vertices_uv_cords = uv_coordinates
					mesh.uv_textures.new(uv_name)
					mesh.uv_layers[-1].data.foreach_set("uv",
														[uv for pair in
														[vertices_uv_cords[loop.vertex_index] for loop in mesh.loops]
														for uv in pair])

				def assign_vertex_groups(input_animation_mapping, vertex_current_mesh):
					# assign vertex groups
					active_object = bpy.context.scene.objects.active
					counter = 0
					armature_object = utils.find_armature()
					n_vertices = vertex_current_mesh.get_num_vertices()

					bone_indices = []
					for vertex_sub_mesh in vertex_current_mesh.subMeshList:
						bone_indices += vertex_sub_mesh.boneIndex

					if len(input_animation_mapping):
						# add armature modifier
						mod = active_object.modifiers.new('Bone Attachment', 'ARMATURE')
						mod.object = armature_object
						mod.use_bone_envelopes = False
						mod.use_vertex_groups = True

						while counter < n_vertices:
							active_object.vertex_groups[input_animation_mapping[bone_indices[counter]]].add([counter],
																											1, 'ADD')
							counter += 1

				# Function Begin
				vertices = []
				faces = []
				uv_list = []
				animation_mapping = []
				for subMesh in input_current_mesh.subMeshList:
					vertices += subMesh.vertices
					faces += subMesh.faces
					uv_list += subMesh.UVs
					animation_mapping += subMesh.animationMapping

				mesh.from_pydata(vertices, [], faces)

				# Update mesh with new data
				mesh.update(calc_edges=True)

				polys = mesh.polygons
				for p in polys:
					p.use_smooth = True

				# assign materials correctly
				if input_current_mesh.nMaterials > 1:
					current_sub_mesh_max_face_index = input_current_mesh.subMeshList[0].nFaces
					sub_mesh_counter = 0
					for face in mesh.polygons:
						if face.index >= current_sub_mesh_max_face_index:
							sub_mesh_counter += 1
							current_sub_mesh_max_face_index += input_current_mesh.subMeshList[sub_mesh_counter].nFaces
						face.material_index = sub_mesh_counter

				# create uv_list
				create_uv_layer("MainUV", uv_list)

				assign_vertex_groups(animation_mapping, input_current_mesh)

			def read_mesh_info(input_current_mesh):

				def create_object(object_current_mesh):
					global mesh
					mesh = bpy.data.meshes.new(object_current_mesh.name)
					new_mesh_object = bpy.data.objects.new(mesh.name, mesh)
					global MeshNameList
					MeshNameList.append(new_mesh_object.name)

					# Link blender_object to scene
					scn = bpy.context.scene
					scn.objects.link(new_mesh_object)
					scn.objects.active = new_mesh_object
					scn.update()

					bpy.context.scene.objects.active = new_mesh_object  # make created blender_object active
					new_mesh_object.show_transparent = True

					if object_current_mesh.isHidden == 1:
						new_mesh_object.Hidden = True

					if object_current_mesh.collision == 1:
						new_mesh_object.HasCollision = True

					# create vertex groups
					armature = utils.find_armature()
					for bone in armature.data.bones:
						new_mesh_object.vertex_groups.new(name=bone.name)

				# Begin Function
				file.seek(8, 1)  # skip proxy_chunk_size and header

				n_materials = struct.unpack("I", file.read(4))[0]
				input_current_mesh.nMaterials = n_materials

				file.seek(24 + 4, 1)  # skip bounding box proxy_chunk_size and unused
				is_hidden = read_int(file.read(4))

				if is_hidden == 1:
					input_current_mesh.isHidden = True

				collision = read_int(file.read(4))
				if collision == 1:
					input_current_mesh.collision = True

				file.seek(88, 1)
				create_object(input_current_mesh)

			def get_mesh_name():
				file.seek(4, 1)  # skip header
				length = read_chunk_length(file)
				counter = 0
				mesh_name = ""
				while counter < length - 1:
					letter = str(file.read(1))
					letter = letter[2:len(letter) - 1]
					mesh_name += letter
					counter += 1
				file.seek(1, 1)  # skip end byte of material_name
				if not main_model:
					mesh_name = "sub" + str(addon_num) + "_" + mesh_name
				return cut_string(mesh_name)

			def read_mesh_data(input_current_sub_mesh):

				def get_n_vertices_n_primitives(numbers_current_sub_mesh):
					numbers_current_sub_mesh.nVertices = read_int(file.read(4))
					numbers_current_sub_mesh.nFaces = read_int(file.read(4))
					file.seek(120, 1)

				def read_animation_mapping(mapping_current_sub_mesh):
					chunk_size = read_chunk_length(file)  # read chunk proxy_chunk_size
					read_counter = chunk_size / 4
					counter = 0
					animation_mapping = []
					while counter < read_counter:
						mapping_current_sub_mesh.animationMapping.append(read_int(file.read(4)))
						counter += 1
					return animation_mapping

				def process_vertex_buffer_2(legacy, buffer_current_sub_mesh):
					for vertex in range(buffer_current_sub_mesh.nVertices):
						co_x = read_float(file.read(4))
						co_y = read_float(file.read(4))
						co_z = read_float(file.read(4))
						buffer_current_sub_mesh.vertices.append(mathutils.Vector((co_x, co_y, co_z)))
						file.seek(12, 1)
						uv_list = [read_float(file.read(4)), read_float(file.read(4)) * -1]
						buffer_current_sub_mesh.UVs.append(uv_list)
						file.seek(64, 1)
						if not legacy:
							file.seek(16, 1)
						buffer_current_sub_mesh.boneIndex.append(read_int(file.read(4)))
						file.seek(28, 1)

				def process_index_buffer(buffer_current_sub_mesh):
					for face_num in range(buffer_current_sub_mesh.nFaces):
						face = [read_u_short(file.read(2)) + buffer_current_sub_mesh.faceOffset,
								read_u_short(file.read(2)) + buffer_current_sub_mesh.faceOffset,
								read_u_short(file.read(2)) + buffer_current_sub_mesh.faceOffset]
						buffer_current_sub_mesh.faces.append(face)

				file.seek(4, 1)  # skip header
				mesh_data_chunk_size = read_chunk_length(file)
				current_position = file.tell()
				while file.tell() < current_position + mesh_data_chunk_size:
					active_chunk = file.read(4)
					if active_chunk == b"\x01\x00\x01\00":
						file.seek(4, 1)  # skip proxy_chunk_size, chunk is always 128 byte
						get_n_vertices_n_primitives(input_current_sub_mesh)
					elif active_chunk == b"\x02\x00\x01\00":
						size = read_chunk_length(file)
						file.seek(size, 1)  # skip to next chunk
					elif active_chunk == b"\x04\x00\x01\00":
						file.seek(4, 1)  # skip proxy_chunk_size
						process_index_buffer(input_current_sub_mesh)
					elif active_chunk == b"\x06\x00\x01\00":
						read_animation_mapping(input_current_sub_mesh)
					elif active_chunk == b"\x07\x00\x01\00":
						file.seek(4, 1)  # skip proxy_chunk_size
						process_vertex_buffer_2(False, input_current_sub_mesh)
					elif active_chunk == b"\x05\x00\x01\00":
						file.seek(4, 1)  # skip proxy_chunk_size
						# old version of the chunk
						process_vertex_buffer_2(True, input_current_sub_mesh)
					elif active_chunk == b"\x00\x12\x00\00":
						size = read_chunk_length(file)
						file.seek(size, 1)  # skip to next chunk

			def read_material_info_chunk(input_current_sub_mesh):

				def set_up_textures(texture_material):

					def setup_mesh_additive():
						# Disconnect output
						links.remove(output.inputs['Surface'].links[0])

						# setup mix shader node
						mix_shader = nodes.new('ShaderNodeMixShader')

						# add transparentBSDF node
						trans_shader = nodes.new('ShaderNodeBsdfTransparent')

						# setup BW converter node
						bw_converter = nodes.new('ShaderNodeRGBToBW')

						# Links: Img->BW->MixFactor; DiffBSDF->MixShader1; TransBSDF->MixShader2; MixShader->OutputSurface
						links.new(bw_converter.inputs['Color'], base_image_node.outputs['Color'])
						links.new(mix_shader.inputs['Fac'], bw_converter.outputs['Val'])

						links.new(mix_shader.inputs['Shader'], diffuse.outputs['BSDF'])
						links.new(mix_shader.inputs[2], trans_shader.outputs['BSDF'])
						links.new(output.inputs['Surface'], mix_shader.outputs['Shader'])

					def setup_mesh_alpha():
						# Disconnect output
						links.remove(output.inputs['Surface'].links[0])

						# setup mix shader node
						mix_shader = nodes.new('ShaderNodeMixShader')

						# add transparentBSDF node
						trans_shader = nodes.new('ShaderNodeBsdfTransparent')

						# Links: ImgAlpha->MixFactor; DiffBSDF->MixShader2; TransBSDF->MixShader1; MixShader->OutputSurface
						links.new(mix_shader.inputs['Fac'], base_image_node.outputs['Alpha'])
						links.new(mix_shader.inputs[2], diffuse.outputs['BSDF'])
						links.new(mix_shader.inputs['Shader'], trans_shader.outputs['BSDF'])
						links.new(output.inputs['Surface'], mix_shader.outputs['Shader'])

					shader_mapping_dict = {'MeshAdditive.fx': setup_mesh_additive, 'MeshAlpha.fx': setup_mesh_alpha}
					texture_material.use_nodes = True
					nt = texture_material.node_tree
					nodes = nt.nodes
					links = nt.links

					# clean up
					while nodes:
						nodes.remove(nodes[0])

					output = nodes.new("ShaderNodeOutputMaterial")
					diffuse = nodes.new("ShaderNodeBsdfDiffuse")

					uv_map = nodes.new("ShaderNodeUVMap")
					uv_map.uv_map = "MainUV"

					created_nodes = [uv_map, diffuse, output]

					if texture_material.BaseTexture != 'None':
						base_image_node = nodes.new("ShaderNodeTexImage")

						links.new(output.inputs['Surface'], diffuse.outputs['BSDF'])
						links.new(diffuse.inputs['Color'], base_image_node.outputs['Color'])
						links.new(base_image_node.inputs['Vector'], uv_map.outputs['UV'])

						if texture_material.BaseTexture in bpy.data.images:
							diffuse_texture = bpy.data.images[texture_material.BaseTexture]
							base_image_node.image = diffuse_texture

						created_nodes.append(base_image_node)

						if texture_material.shaderList.shaderList in shader_mapping_dict:
							shader_mapping_dict[texture_material.shaderList.shaderList]()

					if texture_material.NormalTexture != 'None':
						normal_image_node = nodes.new("ShaderNodeTexImage")
						normal_map_node = nodes.new("ShaderNodeNormalMap")

						normal_map_node.space = 'TANGENT'
						normal_map_node.uv_map = 'MainUV'

						links.new(normal_image_node.outputs['Color'], normal_map_node.inputs['Color'])
						links.new(normal_map_node.outputs['Normal'], diffuse.inputs['Normal'])
						links.new(normal_image_node.inputs['Vector'], uv_map.outputs['UV'])

						if texture_material.NormalTexture in bpy.data.images:
							normal_texture = bpy.data.images[texture_material.NormalTexture]
							normal_image_node.image = normal_texture

					# distribute nodes along the x axis
					for index, node in enumerate(created_nodes):
						node.location.x = 200.0 * index

					if texture_material.NormalTexture != 'None':
						normal_map_node.location = diffuse.location
						normal_map_node.location.y += 300.0
						if texture_material.BaseTexture != 'None':
							normal_image_node.location = base_image_node.location
							normal_image_node.location.y += 300.0

					output.location.x += 200.0
					diffuse.location.x += 200.0

				def process_texture_chunk(texture_material):
					file.seek(5, 1)  # skip chunk proxy_chunk_size and child header
					length = read_u_short(file.read(1) + b'\x00')  # get string chunk_length
					global texture_function_name
					texture_function_name = ""

					for pos in range(length - 1):
						letter = str(file.read(1))
						letter = letter[2:len(letter) - 1]
						texture_function_name = texture_function_name + letter

					file.seek(1, 1)  # skip string end byte
					file.seek(1, 1)  # skip child header
					length = read_u_short(file.read(1) + b'\x00')  # get string chunk_length
					texture_name = ""
					for pos in range(length - 1):
						letter = str(file.read(1))
						letter = letter[2:len(letter) - 1]
						texture_name = texture_name + letter

					# replace texture format with .dds
					if texture_name != "None":
						texture_name = texture_name[0:-4] + ".dds"

					file.seek(1, 1)  # skip string end byte

					load_image(texture_name)
					exec('texture_material.' + texture_function_name + '= texture_name')

				def create_material(material_sub_mesh):  # create texture_material and assign
					shader_name = read_string()
					obj = bpy.context.object
					mat = bpy.data.materials.new(obj.name + "Material")

					if not (shader_name in settings.material_parameter_dict):
						print("Warning: unknown shader: " + shader_name + " setting shader to alDefault.fx")
						shader_name = "alDefault.fx"

					mat.shaderList.shaderList = shader_name

					obj.data.materials.append(mat)
					material_sub_mesh.material = mat

				def read_mat_int(texture_material):
					file.seek(4, 1)  # skip proxy_chunk_size
					material_name = read_string_mini_chunk()
					file.seek(2, 1)  # skip mini header and proxy_chunk_size

					if validate_material_prop(material_name):
						exec('texture_material.' + material_name + '= read_int(file.read(4))')
					else:
						file.seek(4, 1)

				def read_mat_float(texture_material):
					file.seek(4, 1)  # skip proxy_chunk_size
					material_name = read_string_mini_chunk()
					file.seek(2, 1)  # skip mini header and proxy_chunk_size

					if validate_material_prop(material_name):
						exec('texture_material.' + material_name + '= read_float(file.read(4))')
					else:
						file.seek(4, 1)

				def read_mat_float3(texture_material):
					file.seek(4, 1)  # skip proxy_chunk_size
					material_name = read_string_mini_chunk()
					file.seek(2, 1)  # skip mini header and proxy_chunk_size
					value = (read_float(file.read(4)), read_float(file.read(4)), read_float(file.read(4)))

					if validate_material_prop(material_name) and value is not None:
						exec('texture_material.' + material_name + '= value')

				def read_mat_float4(texture_material):
					file.seek(4, 1)  # skip proxy_chunk_size
					material_name = read_string_mini_chunk()
					file.seek(2, 1)  # skip mini header and proxy_chunk_size
					value = (read_float(file.read(4)), read_float(file.read(4)), read_float(file.read(4)),
							read_float(file.read(4)))

					if validate_material_prop(material_name) and value is not None:
						exec('texture_material.' + material_name + '= value')

				file.seek(4, 1)  # skip header
				material_chunk_size = read_chunk_length(file)
				current_position = file.tell()
				while file.tell() < current_position + material_chunk_size:
					active_chunk = file.read(4)
					if active_chunk == b"\x01\x01\x01\00":
						create_material(input_current_sub_mesh)
					elif active_chunk == b"\x02\x01\x01\00":
						read_mat_int(input_current_sub_mesh.material)
					elif active_chunk == b"\x03\x01\x01\00":
						read_mat_float(input_current_sub_mesh.material)
					elif active_chunk == b"\x04\x01\x01\00":
						read_mat_float3(input_current_sub_mesh.material)
					elif active_chunk == b"\x05\x01\x01\00":
						process_texture_chunk(input_current_sub_mesh.material)
					elif active_chunk == b"\x06\x01\x01\00":
						read_mat_float4(input_current_sub_mesh.material)
				set_up_textures(input_current_sub_mesh.material)

			# BEGIN FUNCTION
			# material_name chunk
			current_mesh = MeshClass()
			meshList.append(current_mesh)
			current_mesh.name = get_mesh_name()

			read_mesh_info(current_mesh)

			face_offset = 0
			for material in range(current_mesh.nMaterials):
				current_sub_mesh = SubMeshClass()
				current_mesh.subMeshList.append(current_sub_mesh)

				current_sub_mesh.faceOffset = face_offset
				read_material_info_chunk(current_sub_mesh)
				read_mesh_data(current_sub_mesh)
				face_offset += current_sub_mesh.nVertices

			construct_mesh(current_mesh)
			name = current_mesh.name
			return name

		# Utility functions

		def cut_string(string):
			# bones have a 63 character limit, this function cuts longer strings with space for .xyz end used by
			# blender to distinguish double material_name
			if len(string) > 63:
				return string[0:59]
			else:
				return string

		def read_string():
			# reads string out of chunk containing only a string
			length = read_chunk_length(file)  # get string chunk_length
			string = ""
			counter = 0
			while counter < length - 1:
				letter = file.read(1).decode(encoding="ASCII")
				string += letter
				counter += 1
			file.seek(1, 1)  # skip end byte of material_name
			return string

		def read_string_mini_chunk():
			file.seek(1, 1)  # skip chunk header
			chunk_length = struct.unpack("<b", file.read(1))[0]
			string = ""
			for cur_byte in range(chunk_length - 1):
				letter = str(file.read(1))
				letter = letter[2:len(letter) - 1]
				string = string + letter

			file.seek(1, 1)  # skip end byte of material_name
			return string

		def hide_lods():
			# hides all but the most detailed LOD in Blender
			for cur_object in bpy.data.objects:
				if cur_object.type == 'MESH':
					# ignore objects that are hidden already
					if not cur_object.hide:
						# check if material_name ends with LOD
						if cur_object.name[len(cur_object.name) - 4:len(cur_object.name) - 1] == 'LOD':
							# check for highest LOD
							lod_counter = 0
							while cur_object.name[:-1] + str(lod_counter) in bpy.data.objects:
								lod_counter += 1
							# hide smaller LODS
							for lod in range(lod_counter - 1):
								bpy.data.objects[cur_object.name[:-1] + str(lod)].hide = True

			# hide blender_object if its a shadow or a collision
			for cur_object in bpy.data.objects:
				if cur_object.type == 'MESH' and len(cur_object.material_slots) != 0:
					shader = cur_object.material_slots[0].material.shaderList.shaderList
					if shader == 'MeshCollision.fx' or shader == 'RSkinShadowVolume.fx' or shader == 'MeshShadowVolume.fx':
						cur_object.hide = True

			# hide objects that are set to not visible
			for cur_object in bpy.data.objects:
				if cur_object.type == 'MESH' and cur_object.Hidden:
					cur_object.hide = True

			# hide blast sections of ships
			for cur_object in bpy.data.objects:
				if cur_object.type == 'MESH' and 'blast' in cur_object.name.lower():
					cur_object.hide = True

		def delete_root():
			armature = utils.find_armature()
			if armature is not None:
				armature.select = True  # select the skeleton
				bpy.context.scene.objects.active = armature

				if bpy.ops.object.mode != 'EDIT':
					bpy.ops.object.mode_set(mode='EDIT')
				if 'Root' in armature.data.edit_bones:
					armature.data.edit_bones.remove(armature.data.edit_bones['Root'])
				bpy.ops.object.mode_set(mode='OBJECT')

		# material utility functions

		def load_image(texture_name):
			if texture_name == 'None' or texture_name in bpy.data.images:
				return
			else:
				path = file.name
				path = os.path.dirname(path)
				path = os.path.join(os.path.dirname(path), "Textures", texture_name)
				if os.path.isfile(path):
					bpy.data.images.load(path)
				else:
					print("Error: Couldn't find texture: " + texture_name)
					return

		def validate_material_prop(name):

			if name in material_props:
				return True
			else:
				print("Unknown material property: " + name)
				return False

		# noinspection PyBroadException
		def load_animations(input_filepath):
			def check_is_subanimation(input_file):
				for item in listdir(animation_path):
					item_ext = item[-4:].lower()
					item = item[0:-4]
					file_no_ext = input_file[0:-4]
					if item.startswith(file_no_ext) and not item == file_no_ext and item_ext == '.alo':
						return False
				return True

			animation_file_name = os.path.basename(input_filepath)[0:-4]

			bpy.context.scene.modelFileName = animation_file_name

			animation_files = []

			for ala_file in listdir(animation_path):
				file_ext = ala_file[-4:].lower()
				if file_ext == ".ala" and ala_file.startswith(file_name):
					if check_is_subanimation(ala_file):
						animation_files.append(ala_file)

			importer = import_ala.AnimationImporter()
			arm = utils.find_armature()
			arm.animation_data_create()

			for animation_file in animation_files:
				try:
					importer.load_animation(os.path.join(animation_path, animation_file))
				except:
					print("Import animation error " + animation_file)

		# noinspection PyShadowingNames
		def get_submodels(input_filename):
			filename = input_filename[:-4]
			file_hierarchy = filename.split('_')

			submodels = []

			for o_item in dir_list:
				item = o_item[:-4]
				if o_item[-4:].lower() != '.alo' or item == filename:
					continue
				is_submodel = False
				item_hierarchy = item.split('_')

				# Check if initial structures are the same up to size of current alo file
				if len(item_hierarchy) > len(file_hierarchy) and item.startswith(filename):
					is_submodel = True

				# noinspection PyTypeChecker
				if is_submodel and (not item_hierarchy[-1].lower().startswith('d')):
					submodels.append(o_item)

			if len(submodels) and submodels[0].lower().endswith('_d.alo'):
				submodels.pop(0)
			return submodels

		def remove_particles():
			set_mode_edit()
			arm_obj = find_armature()
			arm_arm = bpy.data.armatures[arm_obj.data.name]
			for bone in arm_arm.edit_bones:
				if bone.name.startswith('p_'):
					arm_arm.edit_bones.remove(bone)
			set_mode_object()

		# VARIABLE TO USE SUBMODEL LOADING
		do_submodels = True

		# Suffixes to ignore when importing
		invalid_suffixes = ['_D']

		global assignedVertexGroups
		assignedVertexGroups = []
		global MeshNameList
		MeshNameList = []
		global doubleMeshes
		doubleMeshes = []
		global boneNameListALO
		boneNameListALO = []
		global boneConnectedDict
		boneConnectedDict = {}

		global meshList
		meshList = []

		global file, file_name, main_model, invalid_suffixes

		main_model = True

		# Read stdin
		self.properties.file_path = sys.stdin.readline().strip()
		self.properties.file_name = os.path.basename(self.properties.file_path)
		self.properties.save_dir = sys.stdin.readline().strip()

		# Read file input, disable animations if needed
		animation_path = sys.stdin.readline().strip()
		if animation_path == "":
			self.importAnimations = False
		base_path = sys.stdin.readline().strip()

		exclude_path = os.path.join(base_path, 'exclude.txt')

		dir_list = listdir(os.path.dirname(self.properties.file_path))

		# Set local variables from properties
		file_path = self.properties.file_path
		file_name = self.properties.file_name
		save_dir = os.path.join(
			os.path.join(self.properties.save_dir, self.properties.file_name[:-4] + ".blend"))

		# Open ALO ala_file
		file = open(file_path, 'rb')  # open ala_file in read binary mode

		bpy.context.scene.render.engine = 'CYCLES'
		import_model()

		if self.importAnimations:
			load_animations(file_path)

		# Get and append sub-files
		if do_submodels:
			submodels = get_submodels(file_name)
			if len(submodels):
				file.close()

				main_model = False

				for addon_num, model in enumerate(submodels):
					print("Importing Submodel: " + model)

					model_name = os.path.join(os.path.dirname(file_path), model)

					self.update_path(model_name)

					file_path = self.properties.file_path
					file_name = self.properties.file_name

					# Open, import, and close the sub model
					file = open(model_name, 'rb')

					try:
						import_model()
					except:
						print("Warning: Import failed for submodel " + model)
						continue
					with open(exclude_path, 'at') as exclude_txt:
						exclude_txt.write(model + '\n')
						exclude_txt.close()

					load_animations(model_name)
					file.close()

		remove_shadow_doubles()
		hide_lods()
		delete_root()
		remove_particles()
		# Replace with export script when complete
		bpy.ops.wm.save_as_mainfile(filepath=save_dir, check_existing=False, relative_remap=False)

		return {'FINISHED'}  # this lets blender know the operator finished successfully.

	# noinspection PyUnusedLocal
	def invoke(self, context, event):

		if self.execute(context) == 'FINISHED':
			print("File Saved, Terminating Blender")

		return {'RUNNING_MODAL'}
