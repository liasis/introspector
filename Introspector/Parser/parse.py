""" Parse Python source code.

This module provides a Parser class that may be used to parse Python source code
and retrieve various information from its abstract syntax tree.

"""

import __builtin__
import ast
import collections
import imp
import keyword
import string

##
# TODO
# - Handle global and nonlocal variables
# - Add support for underlining builtin variables and functions
# - Fix underlining variables in comprehensions
#       - Currently the first name in the comp is considered part of the outside
#         scope, when it should be linked with the next name
##

##
# \brief A namedtuple containing information about a function/class definition.
#
# \details The namedtuple has five fields: title (first line of definition),
#          range (the line range), docstring, and type (one of function, class,
#          or method).
#
_Definition = collections.namedtuple('_Definition', ['title', 'range',
                                                     'docstring', 'type'])
                                                   
##
# \brief A namedtuple containing information about a navigation item.
#
# \details The namedtuple has two fields: name and type (as in _Definition).
#
NavigationItem = collections.namedtuple('NavigationItem', ['name', 'type'])


##
# \brief A namedtuple containing information about a variable location.
#
# \details The namedtuple has two fields: lineno and col_offset.
#
_VariableNode = collections.namedtuple('NavigationItem',
                                       ['lineno', 'col_offset'])


class Parser(object):
    """ Provides an interface for parsing Python source code.
    
    This class uses the source code string of Python code to generate an
    abstract syntax tree for parsing. It provides several methods for retrieving
    information about the tree, including variables defined and documentation
    for functions and classes.
    
    """

    def __init__(self, source=""):
        """ Initialize the Parser class.

        Keyword arguments:
            source -> The source code string.

        """

        self._tree = None
        self._source = None
        self.source = source
        
    @property
    def source(self):
        """ Return the source code string. """

        return self._source
        
    @source.setter
    def source(self, new_source):
        """ Set and parse the source code.
        
        If parsing the source fails, the source is not set, the tree is not
        updated, and an exception is raised from the ast.parse method.
        
        """

        self._tree = ast.parse(new_source)
        self._source = unicode(new_source, 'UTF-8')
        
    @property
    def tree(self):
        """ Return an abstract syntax tree of the source string. """

        return self._tree

    def variables(self, index):
        """ Return a dict of defined variable names mapped to their index.

        From the tree, extract all variable names from assignments and add all
        Python keywords and function names that were not previously defined.
        Parsing is done by finding the path that the index is on (by converting
        it to a line number) after moving the line number backwards to the
        previous non-whitespace-only line. Builtin variables are mapped to -1.

        Arguments
            index -> the index defining the scope of the search.

        """

        # find previous line with any non-whitespace characters
        lineno = self._calculate_lineno(index)
        lines = self._source.splitlines()[:lineno]
        while lines and (lines[-1] == "" or lines[-1].isspace()):
            lines.pop()
        new_lineno = len(lines)

        # parse path in tree with node at line number
        parser = _AssignParser()
        parser.lineno = new_lineno
        path = _get_path(self._tree, new_lineno)
        for node in path:
            parser.visit(node)

        # calculate node index from line number and column offset
        variables = {name: set(_calculate_index(self._source, node.lineno,
                                                node.col_offset)
                               for node in nodes)
                     for (name, nodes) in parser.variables.items()}

        # add builtins
        builtins = dir(__builtin__) + keyword.kwlist
        for builtin in builtins:
            if builtin not in variables:
                variables[builtin] = []

        return {variable: (max(indices) if indices else -1)
                for (variable, indices) in variables.items()}

    def variable_indices(self, index):
        """ Return a list of ranges for where the variable at index is used.

        This method finds the variable name at the index and parses the tree
        to find its scope. The scope is bounded by its first definition before
        index and its first defintion after index (in the case of redefinition).
        Each entry in the returned list is a 2-tuple with (index, length), where
        length is the length of the variable.

        Return an empty list if the index is out of bounds of the source, if no
        word is at the index, or if the variable has not yet been defined.

        """

        # Check index
        if index < 0 or index >= len(self._source):
            return []

        # find variable name
        variable = self._word_at_index(index)
        if not variable:
            return []

        # find node defining the scope of the variable
        lineno = self._calculate_lineno(index)
        path = _get_path(self._tree, lineno)
        scope_nodes = [node for node in reversed(path) if
                       isinstance(node, (ast.Module, ast.FunctionDef,
                                         ast.ClassDef))]
        scope_parser = _AssignParser(float('inf'))
        for scope_node in scope_nodes:
            scope_parser.visit(scope_node)
            if variable in scope_parser.variables:
                break
            scope_parser.variables.clear()
        else:
            return []  # the variable name was not defined on the path

        # find bounding definitions of variable in scope
        variable_indices = sorted(_calculate_index(self._source, node.lineno,
                                                   node.col_offset)
                                  for node in scope_parser.variables[variable])
        prev_index = next((idx for idx in reversed(variable_indices)
                           if idx <= index), 0)
        next_index = next((idx for idx in variable_indices if idx > index),
                          float('inf'))

        # find ranges of all variable names within the scope
        name_parser = _NameParser(variable)
        name_parser.visit(scope_node)
        name_indices = [_calculate_index(self._source, node.lineno,
                                         node.col_offset)
                        for node in name_parser.names]
        return [(idx, len(variable)) for idx in name_indices if
                prev_index <= idx < next_index]
    
    def documentation(self):
        """ Return the documentation of functions and classes in an ast.

        Extract the function names, class names, and all docstrings.

        """

        def def_string(node, name):
            """ Return a string of function line number, name and docstring. """
            
            return "{0} {1}\n{2}".format(node.lineno, name,
                                         ast.get_docstring(node) or "")
        
        functions = {node.name: node for node in self._tree.body if
                     isinstance(node, ast.FunctionDef)}
        for (i, name) in enumerate(functions):
            node = functions[name]
            functions[name] = def_string(node, name)
            if i <= len(functions) - 1:
                functions[name] += "\n\n"

        classes = {node.name: node for node in self._tree.body if
                   isinstance(node, ast.ClassDef)}
        for (i, name) in enumerate(classes):
            node = classes[name]
            classes[name] = def_string(node, name)
            if i <= len(classes) - 1:
                functions[name] += "\n\n"

        documentation = "Functions\n\n"
        function_names = functions.keys()
        function_names.sort()
        class_names = classes.keys()
        class_names.sort()
        for name in function_names:
            documentation += functions[name]

        documentation += "Classes\n\n"
        for name in class_names:
            documentation += classes[name]

        return documentation
        
    def navigation(self):
        """ Return a dict navigatable sections in the source code. 
        
        Dict keys are the line ranges of the navigation item mapped to a
        NavigationItem containing the name, including the parenthesized function
        arguments/subclasses, and definition type.
        
        """

        visitor = _DefinitionParser(self._source)
        visitor.visit(self._tree)
        return {item.range: NavigationItem(name=item.title, type=item.type)
                for item in visitor.definitions}

    def nestable_lines(self):
        """ Return the range of lines that are nestable.

        Parse the tree for all start and end lines of a nestable group (e.g. a
        function defintion or if statement). For each, return a tuple of the
        start and end line number.

        """

        nests = []
        nodes = [ast.walk(node) for node in self._tree.body]
        for node in nodes:
            end = 0
            for subnode in node:
                if isinstance(subnode, (ast.FunctionDef, ast.ClassDef, ast.If,
                                        ast.For, ast.TryExcept,
                                        ast.TryFinally)):
                    end = 0
                    for subsubnode in ast.walk(subnode):
                        try:
                            lineno = subsubnode.lineno
                        except AttributeError:
                            pass
                        else:
                            if lineno > end:
                                end = lineno
                    nests.append((subnode.lineno, end))
        return nests

    def modules(self):
        """ Return a dict of module names and module info.

        Each value of the dict is a list of functions and classes as returned by
        get_functions() and get_classes().

        """

        modules = {}
        for node in self._tree.body:
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Import):
                    module_name = subnode.names[0].name
                elif isinstance(subnode, ast.ImportFrom):
                    module_name = subnode.module
                    imported_name = subnode.names[0].name
                else:
                    continue

                try:
                    module_tree = _parse_module(module_name)
                except TypeError:  # .so files
                    loaded_module = imp.load_dynamic(
                        module_name, imp.find_module(module_name)[1])
                    module_info = dir(loaded_module)
                except IOError:  # directories
                    loaded_module = imp.load_package(
                        module_name, imp.find_module(module_name)[1])
                    module_info = dir(loaded_module)
                else:
                    module_info = self._functions() + self._classes()
                finally:
                    if isinstance(subnode, ast.ImportFrom):
                        if imported_name in module_info:
                            modules[imported_name] = module_info[imported_name]
                    else:
                        modules[module_name] = module_info
        return modules

    def _calculate_lineno(self, index):
        """ Return the line number that contains the given index. """

        lines = self._source.splitlines(True)
        if lines:
            idx = 0
            for (lineno, line) in enumerate(lines):
                idx += len(line)
                if idx >= index:
                    break
            return lineno + 1
        else:
            return 1

    def _word_at_index(self, index):
        """ Return the word at an index or an empty string if in a boundary. """

        chars = string.letters + string.digits + '_'
        anchor = next((idx + 1 for idx in reversed(xrange(index + 1))
                       if self._source[idx] not in chars), 0)
        bound = next((idx for idx in xrange(index, len(self._source))
                      if self._source[idx] not in chars), len(self._source))
        return self._source[anchor:bound]
        
        
class _DefinitionParser(ast.NodeVisitor):
    """ A NodeVisitor subclass to parse an ast for function/class definitions.
    
    Visit all function and class definitions. For class definitions, visit all
    children and assign their type as a method.
    
    """

    def __init__(self, source):
        """ Initialize the object.

        Arguments
            source -> the source code string.

        """

        self.definitions = []
        self._source = source
        
    def visit_FunctionDef(self, node):
        """ Add the definition of a function.

        The visited node is added as a _Definition namedtuple. If there is not a
        docstring, return an empty string instead. The node's children are
        visited with generic_visit.

        """

        self.definitions.append(self._visit_def(node, 'function'))
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        """ Add the definition of a class.
        
        The visited node is added as a _Definition namedtuple. If there is not a
        docstring, return an empty string instead. The node's children are
        visited and functions are added with type method.
        
        """

        self.definitions.append(self._visit_def(node, 'class'))

        # visit children to find methods
        for subnode in ast.iter_child_nodes(node):
            if isinstance(subnode, ast.FunctionDef):
                self.definitions.append(self._visit_def(subnode, 'method'))
            self.generic_visit(subnode)

    def _visit_def(self, node, def_type):
        """ Return a _Definition namedtuple for a FunctionDef or ClassDef node.

        First, determine the line number of the node. Nodes may begin with
        decorators. Therefore, search from the starting line number of the node
        until reaching the definition title.

        Then, get the title of the node. The title is the first line of the
        definition with the 'def' or 'class' stripped off. If the line contains
        the full definition (i.e., ends in a colon), strip that off too.
        Otherwise, end with ellipses.

        Arguments
            node -> the node to visit. It must be one of ast.FunctionDef or
                    ast.ClassDef.
            def_type -> a string representing the type of definition (function,
                        class, or method).

        """

        # determine line prefix
        if isinstance(node, ast.FunctionDef):
            prefix = 'def '
        elif isinstance(node, ast.ClassDef):
            prefix = 'class '
        else:
            raise ValueError(node)

        # find starting lineno, skipping decorators
        lineno = node.lineno
        for line in self._source.splitlines()[node.lineno-1:]:
            if line.strip().startswith(prefix):
                break
            lineno += 1

        # get title
        title = self._source.splitlines()[lineno-1].strip()

        # strip off opening keyword and handle end of title
        title = title[len(prefix):]
        if title.endswith(':'):
            title = title[:-1]
        else:
            title += ' ...'

        # return _Definition namedtuple
        end_lineno = self._node_end(node)
        return _Definition(title=title,
                           range=(lineno, end_lineno - lineno + 1),
                           docstring=ast.get_docstring(node) or '',
                           type=def_type)

    @staticmethod
    def _node_end(node):
        """ Return the ending line number of a node.

        The end line number is calculated by visiting all subnodes using the
        ast.walk function from the input argument node and set to the visited node
        with the highest line number.

        Arguments:
            node -> the node. It must have a lineno attribute.

        """

        end_lineno = node.lineno
        for child in ast.walk(node):
            try:
                lineno = child.lineno
            except AttributeError:
                continue
            if lineno > end_lineno:
                end_lineno = lineno
        return end_lineno


class _NameParser(ast.NodeVisitor):
    """ A NodeVisitor subclass that parses an ast for nodes matching a name. """
    
    def __init__(self, name):
        """ Initialize the object with a name to find in the tree. """

        self.name = name
        self.names = set()

    def visit_Name(self, node):
        """ Visit a name. """

        self._add_node(node, node.id)

    def _visit_def(self, node):
        """ Add the definition's name and generic_visit it.

        The col_offset of the node is incremented to account for the def or
        class string preceding the name of the definition.

        """

        if isinstance(node, ast.FunctionDef):
            node.col_offset += len('def ')
        elif isinstance(node, ast.ClassDef):
            node.col_offset += len('class ')
        self._add_node(node, node.name)
        self.generic_visit(node)

    visit_FunctionDef = _visit_def
    visit_ClassDef = _visit_def

    def _add_node(self, node, name):
        """ Add a node to the names dict. 

        Create a _VariableNode namedtuple and add it to the set at the key
        'name' in the dict.

        """

        if name == self.name:
            self.names.add(_VariableNode(lineno=node.lineno,
                                         col_offset=node.col_offset))


class _AssignParser(ast.NodeVisitor):
    """ A NodeVisitor subclass that parses an ast for assignment variables.
    
    Assignment variables are only saved if within the scope at a given line
    number. 
    
    """

    def __init__(self, lineno=0):
        """ Initialize the object with a line number. 
        
        Keyword arguments:
            lineno -> the line number defining the parse scope.

        """
    
        self.variables = collections.defaultdict(list)
        self.lineno = lineno

    def visit(self, node):
        """ Visit a node if its line number is <= self.lineno. """

        if (hasattr(node, 'lineno') and node.lineno <= self.lineno or
                not hasattr(node, 'lineno')):
            super(_AssignParser, self).visit(node)

    def visit_Module(self, node):
        """ Visit a module.
        
        Add all defined variables and function/class definitions. Definition
        names are added to the variables dict. Other nodes are visited with the
        visit method.

        """
        
        for subnode in node.body:
            if isinstance(subnode, (ast.FunctionDef, ast.ClassDef)):
                self._add_node(subnode, subnode.name)
            else:
                self.visit(subnode)
    
    def visit_Assign(self, node):
        """ Process all targets of an assignment.
        
        This method uses the _visit_assign_target instance method.
        
        """
        
        for target in node.targets:
            self._visit_assign_target(target)
        self.generic_visit(node)
        
    def visit_For(self, node):
        """ Visit a for loop.
        
        Store all variables defined in its body as well as the variables
        targeted in the loop definition.
        
        """

        self._visit_assign_target(node.target)
        self.generic_visit(node)

    def _visit_comprehension(self, node):
        """ Visit a list, dict, set, or genexp comprehension. 
        
        Iterate over all of the node's generators, visit the target
        (the 'x' in "...for x in..."), and add them to the variables list.
        If the target is a tuple, visit its elts.
        
        """
        
        for comprehension in node.generators:
            try:
                name = comprehension.target.id
            except AttributeError:
                for elt in comprehension.target.elts:
                    self._add_node(elt, elt.id)
            else:
                self._add_node(comprehension.target, name)
    
    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension

    def _visit_def(self, node):
        """ Visit a function/class definition.
        
        Visit all nodes in the definition body. If one of these subnodes is
        another definition, only add its name to the variables list. Otherwise,
        visit it normally. Add the name of the definition node to the variables
        list.
        
        """

        for subnode in node.body:
            if (isinstance(subnode, (ast.FunctionDef, ast.ClassDef)) and
                subnode.lineno <= self.lineno):
                    self._add_node(subnode, subnode.name)
            else:
                self.visit(subnode)
        self._add_node(node, node.name)
    
    def visit_FunctionDef(self, node):
        """ Visit a function definition. 
        
        This method uses the _visit_def instance method. If the node line number
        is less than self.lineno, add all argument names to the variables list.
        
        """
        
        self._visit_def(node)
        if node.lineno < self.lineno:
            for arg in node.args.args:
                self._add_node(arg, arg.id)
        
    visit_ClassDef = _visit_def
    
    def _visit_import(self, node):
        """ Visit an import or import from statement.
        
        If the module is imported as another name, store that variable name;
        otherwise, store the module name.

        """
        
        for name in node.names:
            if name.asname:
                self._add_node(node, name.asname)
            else:
                self._add_node(node, name.name)
    
    visit_Import = _visit_import
    visit_ImportFrom = _visit_import

    def _visit_assign_target(self, node):
        """ Visit an assignment target.
        
        Store the name or, if it is a tuple, all names within the tuple.
        
        """
        
        try:
            name = node.id
        except AttributeError:
            if isinstance(node, ast.Tuple):
                for elt in node.elts:
                    self._add_node(elt, elt.id)
        else:
            self._add_node(node, name)

    def _add_node(self, node, name):
        """ Add a node to the variables dict.
        
        Create a _VariableNode namedtuple and add it to the set at the key
        'name' in the dict.
        
        """
        
        self.variables[name].append(_VariableNode(lineno=node.lineno,
                                                  col_offset=node.col_offset))


def _iter_paths(tree, cur=()):
    """ Return a generator of all paths in the abstract syntax tree. 
    
    Recursively yields each path through the tree.
    
    Arguments:
        tree -> the abstract syntax tree to search
        
    Keyword arguments:
        cur -> a tuple storing the walked path. Used for recursive calls.
    
    """
    
    children = list(ast.iter_child_nodes(tree))
    if not children:
        yield cur
    else:
        for child in children:
            for path in _iter_paths(child, cur + (child,)):
                yield path
            
            
def _get_path(tree, lineno):
    """ Return the path in a tree that terminates at a line number. 
    
    Follow all paths in a tree using _iter_paths until finding one where a node
    is on the desired line number. The path is a tuple of nodes, including the
    root ast.Module node. If no node is found with the particular line number,
    return an empty tuple.
    
    Arguments:
        tree -> the abstract syntax tree to search
        lineno -> the line number
    
    """
    
    for path in list(_iter_paths(tree)):
        for node in path:
            try:
                node_lineno = node.lineno
            except AttributeError:
                pass
            else:
                if node_lineno == lineno:
                    return (tree,) + path
    return ()
    

def _calculate_index(source, lineno, col_offset):
    """ Return the index of a substring given a lineno and column.

    Arguments:
        source -> The source code string.
        lineno -> The line number.
        col_offset -> The column offset

    """

    lines = source.splitlines(True)
    return sum(len(line) for line in lines[:lineno-1]) + col_offset


def _parse_module(name):
    """ Return an ast of the module at the absolute path. """

    hierarchy = name.split('.')
    name = hierarchy.pop()
    if hierarchy:
        pkg_path = _package_path(hierarchy)
        module = imp.find_module(name, [pkg_path])
    else:
        module = imp.find_module(name)
    tree = ast.parse(''.join(module[0].readlines()))
    module[0].close()
    return tree


def _package_path(hierarchy, pkg_path=None):
    """ Return the path of a package.

    Recursively search the hierarchy inwards to find the path of the innermost
    entry.

    Arguments:
        hierarchy -> the result of package.split('.'), where package is the
            absolute import name.

    Keyword Arguments:
        pkg_path -> May use this to begin the search path at a directory, but
            its main purpose is for recursive calls to the function.

    """

    if pkg_path:
        pkg_path = [pkg_path]
    if (len(hierarchy) == 1):
        return imp.find_module(hierarchy[0], pkg_path)[1]
    parent = hierarchy.pop(0)
    parent_path = imp.find_module(parent, pkg_path)[1]
    return _package_path(hierarchy, parent_path)
