#
#    Copyright (C) 2011 Ondrej Meca
#
#    This file is part of Kaira.
#
#    Kaira is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License, or
#    (at your option) any later version.
#
#    Kaira is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Kaira.  If not, see <http://www.gnu.org/licenses/>.
#
import utils
import os
from project import Project, ExternType, Function, Parameter

class ProjectJava(Project):
    
    def __init__(self, file_name, language):
        Project.__init__(self, file_name)
        self.language = language
        self.build_options = {
            "JFLAGS" : "-g",
            "JC" : "javac",
            "LIBS" : ""
        }
        self.language_class = {
            "extern_type" : ExternTypeJava,
            "function" : FunctionJava,
            "parameter" : Parameter
        }
        
    def get_language(self):
        return self.language
    
    def get_language_of_manager(self):
        """return language for GtkSourceView"""
        return "java"

    def get_emitted_source_filename(self):
        return self.get_filename_without_ext() + ".java"
    
    def get_head_filename(self):
        return os.path.join(self.get_directory(), "head.java")
    
    def write_content_to_head_file(self):
        return """/* This file is included at the beginning of the main source file,\n\
               so definitions from this file can be used in functions in\n\
               transitions and places. */\n\n"""
            
    def type_to_lang_type(self, t):
        if t == "__Context":
            return "CaContext"
        if t == "Int":
            return "int"
        if t == "Bool":
            return "boolean"
        if t == "Float":
            return "float"
        if t == "Double":
            return "double"
        if t == "String":
            return "String"
        for et in self.extern_types:
            if et.get_name() == t:
                return et.get_raw_type()
        return None
    
    def get_source_file(self):
        return ["*.java"]

    def write_makefile(self):
        makefile = utils.Makefile()
        makefile.set_top_comment("This file is autogenerated.\nDo not edit directly this file.")
        makefile.set("JFLAGS", self.get_build_option("JFLAGS"))
        makefile.set("JC", self.get_build_option("JC"))
        
        makefile.rule(".SUFFIXES", [".java", ".class"])
        makefile.rule(".java.class", "", "$(JC) $(JFLAGS) $*.java")
        
        if self.get_build_option("OTHER_FILES"):
            other_deps = [ os.path.splitext(f)[0] + ".java" for f in self.get_build_option("OTHER_FILES").split("\n") ]
        else:
            other_deps = []
            
        name_source = self.get_name() + ".java"
        name_head = "head.java"
        classes = name_source + " " + name_head
        for c in other_deps:
            classes = classes + " " + c
        
        makefile.set("CLASSES", classes)
        
        makefile.rule("default", [ "classes" ])
        makefile.rule("classes", [ "$(CLASSES:.java=.class)" ])
        makefile.rule("clean", "", "$(RM) *.class")
        
        makefile.write_to_file(os.path.join(self.get_directory(), "makefile"))
        
        
class ExternTypeJava(ExternType):
    
    def __init__(self, name = "", raw_type = "", transport_mode = "Disabled"):
        ExternType.__init__(self, name, raw_type, transport_mode)
        

    def get_default_function_code(self):
        return "\treturn \"" + self.name + "\";\n"
        
    def get_function_declaration(self, name):
        if name == "getstring":
            return "String getstring(" + self.raw_type + " obj)"
        elif name == "getsize":
            return "int getsize(" + self.raw_type + " obj)"
        elif name == "pack":
            return "void pack(CaPacker packer, " + self.raw_type + " obj)"
        elif name == "unpack":
            return self.raw_type + " unpack(CaUnpacker unpacker)"
        
        
class FunctionJava(Function):
    
    def __init__(self, id = None):
        Function.__init__(self, id)
        
    def get_function_declaration(self):
        return self.get_lang_return_type() + " " + self.name + "(" + self.get_lang_parameters() + ")"    
        
    def get_lang_parameters(self):
        p = self.split_parameters()
        if p is None:
            return "Invalid format of parameters"
        else:
            params_str =    [ self.project.type_to_lang_type(t) + " " + n for (t, n) in p ]
            if self.with_context:
                params_str.insert(0, "CaContext ctx")
            return ", ".join(params_str)    
        
    def get_lang_return_type(self):
        return self.project.type_to_lang_type(self.return_type)    
    