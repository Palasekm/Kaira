from net import Net, load_net, ExportException
import xml.etree.ElementTree as xml
import utils
import copy
import os
import paths
from events import EventSource

class Project(EventSource):
	""" 
		Events: changed, filename_changed
	"""
	
	def __init__(self, file_name):
		assert file_name is not None
		EventSource.__init__(self)
		self.id_counter = 100
		self.set_filename(file_name)
		self.parameters = []
		self.extern_types = []
		self.param_values_cache = None
		self.error_messages = {}
		self.events = [
			Event("node_init", "void", "CaContext *ctx"),
			Event("node_quit", "void", "CaContext *ctx")
		]

	def new_id(self):
		self.id_counter += 1
		return self.id_counter

	def set_net(self, net):
		self.net = net
		net.set_change_callback(self._net_changed)
		self.changed()

	def copy(self):
		return load_project_from_xml(self.as_xml(), self.filename)

	def get_name(self):
		d, fname = os.path.split(self.filename)
		name, ext = os.path.splitext(fname)
		return name

	def get_filename(self):
		return self.filename

	def get_filename_without_ext(self):
		name, ext = os.path.splitext(self.filename)
		return name

	def get_executable_filename(self):
		return self.get_filename_without_ext()

	def get_exported_filename(self):
		return self.get_filename_without_ext() + ".xml"

	def get_emitted_source_filename(self):
		return self.get_filename_without_ext() + ".cpp"

	def get_head_filename(self):
		return os.path.join(self.get_directory(), "head.cpp")

	def get_directory(self):
		return os.path.dirname(self.filename)

	def set_filename(self, filename):
		self.filename = os.path.abspath(filename)
		self.emit_event("filename_changed")

	# Cache is used for rerunning simulation with same parameters
	def get_param_value_cache(self):
		return self.param_values_cache

	def set_param_values_cache(self, param_values):
		self.param_values_cache = param_values

	def reset_param_values_cache(self):
		self.param_values_cache = None

	def set_error_messages(self, messages):
		self.error_messages = messages
		self.changed()

	def has_error_messages(self, item):
		return item.get_id() in self.error_messages

	def get_error_messages(self, item):
		if item.get_id() in self.error_messages:
			return self.error_messages[item.get_id()]
		else:
			return None

	def changed(self):
		self.emit_event("changed")

	def _net_changed(self, net):
		self.changed()

	def as_xml(self):
		root = xml.Element("project")
		root.append(self._configuration_element())

		xml_net = self.net.as_xml()
		root.append(xml_net)
		return root

	def save(self):
		assert self.filename is not None
		f = open(self.filename, "w")
		try:
			f.write(xml.tostring(self.as_xml()))
		finally:
			f.close()

	def export(self, filename):
		root = xml.Element("project")

		root.append(self._configuration_element())

		xml_nets = self.net.export_xml()
		for e in xml_nets:
			root.append(e)

		f = open(filename, "w")
		try:
			f.write(xml.tostring(root))
		finally:
			f.close()

	def get_extern_types(self):
		return self.extern_types

	def get_events(self):
		return self.events

	def get_event(self, name):
		for e in self.events:
			if e.get_name() == name:
				return e
		raise "Event '" + name + "' not found"

	def new_extern_type(self):
		obj = ExternType()
		self.extern_types.append(obj)
		self.changed()
		return obj

	def remove_extern_type(self, obj):
		self.extern_types.remove(obj)
		self.changed()

	def new_parameter(self):
		self.reset_param_values_cache()
		p = Parameter()
		p.set_callback("changed", self.reset_param_values_cache)
		self.parameters.append(p)
		self.changed()
		return p

	def get_parameters(self):
		return self.parameters

	def remove_parameter(self, parameter):
		self.reset_param_values_cache()
		self.parameters.remove(parameter)
		self.changed()

	def write_project_files(self):
		self.write_makefile()
		utils.write_file_if_not_exists(self.get_head_filename(),
			"/* This file is included at the beginning of main source file,\n" + 
			"   so definition from this file can be used in functions in\n" +
			"   transitions and places. */\n\n")

	def write_makefile(self):
		makefile = utils.Makefile()
		makefile.set_top_comment("This file is autogenerated.\nDo not edit directly this file.")
		makefile.set("CC", "g++")
		makefile.set("CFLAGS", "-O2")
		makefile.set("LIBDIR", "-L" + paths.CAILIE_DIR)
		makefile.set("LIB", "-lcailie -lpthread")
		makefile.set("INCLUDE", "-I" + paths.CAILIE_DIR)

		makefile.rule("all", [self.get_name()])
		deps = [ self.get_name() + ".o" ]
		makefile.rule(self.get_name(), deps, "$(CC) " + " ".join(deps) + " -o $@ $(CFLAGS) $(INCLUDE) $(LIBDIR) $(LIB) " )
		makefile.rule(".cpp.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")
		makefile.rule("clean", [], "rm -f *.o " + self.get_name() + " ")
		makefile.write_to_file(os.path.join(self.get_directory(), "makefile"))

	def _configuration_element(self):
		e = xml.Element("configuration")
		for p in self.parameters:
			e.append(p.as_xml())
		for t in self.extern_types:
			e.append(t.as_xml())
		for t in self.events:
			if t.has_code():
				e.append(t.as_xml())
		return e

class Parameter(EventSource):
	"""
		Events: changed
	"""

	def __init__(self):
		EventSource.__init__(self)
		self.name = ""
		self.type = "Int"
		self.description = ""

	def set_name(self, name):
		self.name = name
		self.changed()

	def get_name(self):
		return self.name

	def set_type(self, type):
		self.type = type
		self.changed()

	def get_type(self):
		return self.type

	def get_description(self):
		return self.description

	def set_description(self, description):
		self.description = description
		self.changed()

	def changed(self):
		self.emit_event("changed")

	def as_xml(self):
		e = xml.Element("parameter")
		e.set("name", self.name)
		e.set("type", self.type)
		e.set("description", self.description)
		return e

class ExternType:
	"""
		Transport modes: "Disabled", "Direct", "Custom"
	"""

	def __init__(self, name = "", raw_type = "", transport_mode = "Disabled"):
		self.name = name
		self.raw_type = raw_type
		self.transport_mode = transport_mode
		self.functions = {
			"getstring": "",
			"getsize": "",
			"pack": "",
			"unpack": ""
		}

	def get_name(self):
		return self.name

	def get_raw_type(self):
		return self.raw_type

	def get_transport_mode(self):
		return self.transport_mode

	def set_name(self, value):
		self.name = value

	def set_raw_type(self, value):
		self.raw_type = value

	def set_transport_mode(self, value):
		self.transport_mode = value

	def set_function_code(self, name, value):
		self.functions[name] = value

	def has_function(self, name):
		return "" != self.functions[name].strip()

	def get_function_code(self, name):
		if self.has_function(name):
			return self.functions[name]
		elif name == "getstring":
			return "\treturn \"" + self.name + "\";\n";
		else:
			return "\t\n"

	def is_function_allowed(self, name):
		if self.transport_mode == "Custom":
			return True
		else:
			return name == "getstring"

	def get_function_list_string(self):
		names = [ name for name in self.functions if self.has_function(name) and self.is_function_allowed(name) ]
		return ", ".join(names)

	def get_function_declaration(self, name):
		if name == "getstring":
			return "std::string getstring(" + self.raw_type + " &obj)"
		elif name == "getsize":
			return "size_t getstring(" + self.raw_type + " &obj)"
		elif name == "pack":
			return "void pack(CaPacker &packer, " + self.raw_type + " &obj)"
		elif name == "unpack":
			return self.raw_type + " unpack(CaUnpacker &unpacker)"


	def as_xml(self):
		e = xml.Element("extern-type")
		e.set("name", self.name)
		e.set("raw-type", self.raw_type)
		e.set("transport-mode", self.transport_mode)

		for name in self.functions:
			if self.has_function(name):
				fe = xml.Element("code")
				fe.set("name", name)
				fe.text = self.functions[name]
				e.append(fe)

		return e

class Event:

	def __init__(self, name, return_type, parameters):
		self.name = name
		self.return_type = return_type
		self.parameters = parameters
		self.code = ""

	def get_name(self):
		return self.name

	def set_function_code(self, code):
		self.code = code

	def get_function_code(self):
		if self.has_code():
			return self.code
		else:
			return "\t\n"

	def has_code(self):
		return self.code.strip() != ""

	def get_function_declaration(self):
		return self.return_type + " " + self.name + "(" + self.parameters + ")"

	def as_xml(self):
		e = xml.Element("event")
		e.set("name", self.name)
		e.text = self.code
		return e

def load_project(filename):
	doc = xml.parse(filename)
	root = doc.getroot()
	project, idtable = load_project_from_xml(root, filename)
	return project

def load_project_from_xml(root, filename):
	project = Project(filename)
	if root.find("configuration"):
		load_configuration(root.find("configuration"), project)
	net, idtable = load_net(root.find("net"), project)
	project.set_net(net)
	return project, idtable

def load_parameter(element, project):
	p = project.new_parameter()
	p.set_name(utils.xml_str(element, "name"))
	p.set_description(utils.xml_str(element, "description", ""))
	p.set_type(utils.xml_str(element, "type"))

def load_extern_type(element, project):
	p = project.new_extern_type()
	p.set_name(utils.xml_str(element, "name"))
	p.set_raw_type(utils.xml_str(element, "raw-type"))
	p.set_transport_mode(utils.xml_str(element, "transport-mode"))

	for e in element.findall("code"):
		name = utils.xml_str(e, "name")
		p.set_function_code(name, e.text)

def load_event(element, project):
	name = utils.xml_str(element, "name")
	event = project.get_event(name)
	event.set_function_code(element.text)

def load_configuration(element, project):
	for e in element.findall("parameter"):
		load_parameter(e, project)
	for e in element.findall("extern-type"):
		load_extern_type(e, project)
	for e in element.findall("event"):
		load_event(e, project)

def new_empty_project(directory):
	os.mkdir(directory)
	name = os.path.basename(directory)
	project_filename = os.path.join(directory,name + ".proj")
	project = Project(project_filename)
	net = Net(project)
	project.set_net(net)
	project.write_project_files()
	project.save()
	return project
