import __builtin__
import keyword
import unittest

import parse

source = """import os

top_var = 1
def func1(arg1, arg2):
    in_arg1 = 2
    def in_func(arg3):
        in_arg2 = 3
        return arg1 + arg3
    return in_func(arg2)

def func2():
    in_arg3 = 1
    in_arg4 = 3
    return in_arg3 + in_arg4

class Cls():
    def __init__(self):
        self.a = 1
        self.b = 2
        print a, b

def func3(arg4):
    if arg4 is None:
        if_arg1 = 1
    else:
        if_arg2 = 2
    
    while arg4:
        while_arg = 1
        
    for for_target in arg4:
        for_arg = 1
        
    try:
        try_arg1 = 1
    except:
        try_arg2 = 2
    else:
        try_arg3 = 3
    finally:
        try_arg4 = 4
    print arg4 
    x = [comp_arg1 for comp_arg1 in arg4]
    x = (comp_arg2 for comp_arg2 in arg4)
    x = {comp_arg3 for comp_arg3 in arg4}
    x = {comp_key: comp_arg4 for (comp_key, comp_arg4) in arg4}
    return

"""

simple_source = """outer = 1
print outer
def func():
    invar = 1
    print invar
    invar = 2
outer = 2
print outer
print invar"""

class TestParse(unittest.TestCase):
    def setUp(self):        
        self.parser = parse.Parser()
        
    def test_variables(self):
        self.parser.source = source
        builtin_vars = list(set(dir(__builtin__) + keyword.kwlist))
        top_vars = (['os', 'func1', 'func2', 'Cls', 'func3'] +
                    builtin_vars)
        func1_vars = ['arg1', 'arg2', 'in_arg1', 'in_func']
        in_func_vars = func1_vars + ['arg3', 'in_arg2']
        func2_vars = ['in_arg3', 'in_arg4']
        init_vars = ['self', '__init__']
        func3_vars = ['arg4', 'if_arg1', 'if_arg2', 'while_arg', 'for_target',
                      'for_arg', 'try_arg1', 'try_arg2', 'try_arg3', 'try_arg4']
                
        # test module-level
        self.assertItemsEqual(self.parser.variables(0), top_vars)
        top_vars.append('top_var')
        for index in [12, 159, 234]:  # lines 3, 11, 16
            self.assertItemsEqual(self.parser.variables(index), top_vars)
            
        # test within functions and classes
        self.assertItemsEqual(self.parser.variables(106),  # line 8
                              top_vars + in_func_vars)
        self.assertItemsEqual(self.parser.variables(133),  # line 9
                              top_vars + func1_vars)
        self.assertItemsEqual(self.parser.variables(204),  # line 14
                              top_vars + func2_vars)
        self.assertItemsEqual(self.parser.variables(309),  # line 20
                              top_vars + init_vars)
        self.assertItemsEqual(self.parser.variables(654),  # line 42
                              top_vars + func3_vars)
        self.assertItemsEqual(self.parser.variables(670),  # line 43
                              top_vars + func3_vars + ['x', 'comp_arg1'])
        self.assertItemsEqual(self.parser.variables(712),  # line 44
                              top_vars + func3_vars +
                              ['x', 'comp_arg1', 'comp_arg2'])
        self.assertItemsEqual(self.parser.variables(754),  # line 45
                              top_vars + func3_vars +
                              ['x', 'comp_arg1', 'comp_arg2', 'comp_arg3'])
        self.assertItemsEqual(self.parser.variables(796),  # line 46
                              top_vars + func3_vars +
                              ['x', 'comp_arg1', 'comp_arg2', 'comp_arg3',
                               'comp_arg4', 'comp_key'])
        
        # test line number in whitespace
        self.assertItemsEqual(self.parser.variables(133),  # line 9 == 10
                              self.parser.variables(158))
        self.assertItemsEqual(self.parser.variables(204),  # line 14 == 15
                              self.parser.variables(233))
        self.assertItemsEqual(self.parser.variables(309),  # line 20 == 21
                              self.parser.variables(328))
                              
        # test empty
        self.parser.source = ""
        self.assertItemsEqual(self.parser.variables(0), builtin_vars)

    def test_variable_indices(self):
        self.parser.source = simple_source

        def ranges(variable, indices):
            return [(index, len(variable)) for index in indices]

        self.assertItemsEqual(self.parser.variable_indices(0),
                              ranges('outer', [0, 16]))
        self.assertItemsEqual(self.parser.variable_indices(38),
                              ranges('invar', [38, 58]))
        self.assertItemsEqual(self.parser.variable_indices(68),
                              ranges('invar', [68]))
        self.assertItemsEqual(self.parser.variable_indices(78),
                              ranges('outer', [78, 94]))

        # test range equality for invar variable
        self.assertItemsEqual(self.parser.variable_indices(38),
                              self.parser.variable_indices(58))
        
        # test final invar definition
        self.assertItemsEqual(self.parser.variable_indices(106), [])
        
                                                  
if __name__ == '__main__':
    unittest.main()
