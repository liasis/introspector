/**
 * \file PLPythonIntrospectionController.m
 * \brief Liasis Python IDE text editor code parser.
 *
 * \details This file contains the public and private methods and interface for
 * the code introspection parser. This class provides methods for parsing and
 * providing information about a Python file.
 *
 * \copyright Copyright (C) 2012-2014 Jason Lomnitz and Danny Nicklas.
 *
 * This file is part of the Python Liasis IDE.
 *
 * The Python Liasis IDE is free software: you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * The Python Liasis IDE is distributed in the hope that it will be
 * useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with the Python Liasis IDE. If not, see <http://www.gnu.org/licenses/>.
 *
 * \author Jason Lomnitz.
 * \author Danny Nicklas
 * \date 2012-2014.
 */

#import "PLPythonIntrospectionController.h"

@implementation PLPythonIntrospectionController

-(id)init
{
        PyObject * pyPath = NULL, * pyParseModule = NULL;
        NSString * localPath = nil;
        int flag = 0;
        const char * introspectionModule = "parse";
        
        self = [super init];
        if (self) {
                pyPath = PySys_GetObject("path");
                localPath = [[NSBundle bundleForClass:[self class]] resourcePath];
                flag = PyList_Append(pyPath, PyString_FromString([localPath UTF8String]));
                if (flag < 0) {
                        NSLog(@"Error in init: could not append local path to Python sys.path");
                        PyErr_Clear();
                        [self release];
                        self = nil;
                        goto exit;
                }

                pyParseModule = PyImport_ImportModule(introspectionModule);
                if (pyParseModule == NULL) {
                        NSLog(@"Error in init: could not import '%s' module", introspectionModule);
                        PyErr_Clear();
                        [self release];
                        self = nil;
                        goto exit;
                }
                
                pyParser = PyObject_CallMethod(pyParseModule, "Parser", NULL);
                if (pyParser == NULL) {
                        NSLog(@"Error in init: could not create Parser object from '%s' module", introspectionModule);
                        [self release];
                        self = nil;
                        goto exit;
                }
        }
        
exit:
        Py_XDECREF(pyParseModule);
        return self;
}

/**
 * \brief Deallocate the introspection controller.
 *
 * \details Decrement the Python Parser object.
 */
-(void)dealloc
{
        Py_XDECREF(pyParser);
        [super dealloc];
}

/**
 * \brief Return the addon type.
 *
 * \return The addon type.
 */
+(PLAddOnType)type
{
        return PLAddOnPythonCodeController;
}

/**
 * \brief Parse the Python source code for its abstract syntax tree.
 *
 * \details Convert the source to a Python string and set the source attribute
 *          of the internal Python Parser object, which triggers parsing of the
 *          source into an abstract syntax tree.
 *
 * \param source The Python source code string.
 *
 * \param error On input, a pointer to a pointer for an error object. If an
 *              error occurs while parsing the source code, this parameter
 *              contains an error object on output unless it was NULL on input.
 *
 * \return A boolean flag indicating whether an error occurred.
 */
-(BOOL)parseSource:(NSString *)source error:(NSError **)error
{
        NSString * errorMessage = nil;
        PyObject * pySource = NULL;
        BOOL successful = YES;
        int flag = 0;
        
        pySource = PyString_FromString([source UTF8String]);
        if (pySource == NULL) {
                errorMessage = @"Could not convert source to Python object.";
                successful = NO;
                goto exit;
        }

        flag = PyObject_SetAttrString(pyParser, "source", pySource);
        if (flag == -1) {
                errorMessage = @"Could not set 'source' of Parser Python object.";
                successful = NO;
                PyErr_Clear();
                goto exit;
        }

exit:
        if (error && errorMessage) {
                *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                             code:PLErrorCodeStatusBar
                                         userInfo:@{NSLocalizedDescriptionKey: errorMessage}];
        }
        Py_XDECREF(pySource);
        return successful;
}

/**
 * \brief Return an array of nestable lines.
 *
 * \details Nestable lines are those indented in the source code. Calls the
 *          nestable_lines() function in parse module. Convert the returned list
 *          of tuples into an NSArray of NSArrays.
 *
 * \param error On input, a pointer to a pointer for an error object. If an
 *              error occurs while getting the nestable lines, this parameter
 *              contains an error object on output unless it was NULL on input.
 *
 * \return The array of nestable lines, where each entry is an array of start
 *         and end line numbers. Return nil on error.
 */
-(NSArray *)getNestableLinesAndReturnError:(NSError **)error
{
        NSArray * nests = nil;
        NSError * arrayError = nil;
        PyObject * pyNests = NULL;
        char * parserMethod = "nestable_lines";
        __block NSError * rangeError = nil;

        pyNests = PyObject_CallMethod(pyParser, parserMethod, NULL);
        if (pyNests == NULL) {
                if (error) {
                        *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                                     code:PLErrorCodeStatusBar
                                                 userInfo:@{NSLocalizedDescriptionKey: [NSString stringWithFormat:@"Could not call '%s' Parser method", parserMethod]}];
                }
                goto exit;
        }
        nests = [NSArray arrayByEnumeratingPythonSequence:pyNests error:&arrayError withBlock:^id(PyObject *obj, NSUInteger idx) {
                NSArray * nestRange = nil;
                
                nestRange = [NSArray arrayByEnumeratingPythonSequence:obj error:&rangeError withBlock:^id(PyObject * nestObj, NSUInteger idx) {
                        long nestRangeValue = PyLong_AsLong(nestObj);
                        if (PyErr_Occurred()) {
                                PyErr_Clear();
                                return nil;
                        }
                        return [NSNumber numberWithLong:nestRangeValue];
                }];
                if (nestRange == nil) {
                        [[rangeError userInfo] setValue:@"Error converting nestable line tuple value to long."
                                                 forKey:NSLocalizedFailureReasonErrorKey];
                        return nil;
                }
                return [NSValue valueWithRange:NSMakeRange([[nestRange objectAtIndex:0] longValue],
                                                           [[nestRange objectAtIndex:1] longValue])];
        }];
        if (nests == nil && error) {
                *error = [NSError errorWithDomain:PLLiasisKitErrorDomain
                                             code:PLErrorCodeStatusBar
                                         userInfo:[arrayError userInfo]];
                [[*error userInfo] setValue:rangeError forKey:NSUnderlyingErrorKey];
                goto exit;
        }
exit:
        Py_XDECREF(pyNests);
        if (nests == nil)
                return nil;
        return [NSArray arrayWithArray:nests];
}

/**
 * \brief Return the defined variables in the Python source, mapped to their
 *        definition index using the index to define the scope.
 *
 * \details Call the variables() method of the Parser object with an index
 *          used to determine the scope of variable definitions.
 *
 * \param index The index in the source string defining the scope of the parse.
 *
 * \param error On input, a pointer to a pointer for an error object. If an
 *              error occurs while getting the variables, this parameter
 *              contains an error object on output unless it was NULL on input.
 *
 * \return A dictionary of variables defined within the scope at the index
 *         mapped to their definition index. Return nil on error.
 */
-(NSDictionary *)variablesWithIndex:(NSUInteger)index error:(NSError **)error
{
        NSDictionary * variables = nil;
        NSError * variablesError = nil;
        PyObject * pyVariables = NULL;
        NSString * errorMessage = @"Error getting introspection variables.";
        char * variablesMethod = "variables";
        __block NSString * variablesErrorMessage = nil;
        
        pyVariables = PyObject_CallMethod(pyParser, variablesMethod, "(k)", index);
        if (pyVariables == NULL) {
                if (error) {
                        *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                                     code:PLErrorCodeStatusBar
                                                 userInfo:@{NSLocalizedDescriptionKey: errorMessage,
                                                            NSLocalizedFailureReasonErrorKey: [NSString stringWithFormat:@"Could not call '%s' function", variablesMethod]}];
                }
                goto exit;
        }

        variables = [NSDictionary dictionaryByEnumeratingPythonDict:pyVariables error:&variablesError withBlock:^PLDictionaryItem *(PyObject * key, PyObject * value) {
                char * variableString = NULL;
                long variableIndex = 0;

                variableString = PyString_AsString(key);
                if (variableString == NULL) {
                        variablesErrorMessage = @"Error converting Python dict key to string.";
                        PyErr_Clear();
                        return nil;
                }
                
                variableIndex = PyLong_AsLong(value);
                if (PyErr_Occurred()) {
                        variablesErrorMessage = @"Error converting Python dict value to long.";
                        PyErr_Clear();
                        return nil;
                }
                return [PLDictionaryItem dictionaryItemWithObject:[NSNumber numberWithLong:variableIndex]
                                                           forKey:[NSString stringWithUTF8String:variableString]];
        }];
        if (variables == nil && error) {
                *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                             code:PLErrorCodeStatusBar
                                         userInfo:@{NSLocalizedDescriptionKey: errorMessage,
                                                    NSUnderlyingErrorKey: variablesError}];
                if (variablesErrorMessage)
                        [*error setValue:variablesErrorMessage forKey:NSLocalizedFailureReasonErrorKey];
        }
        
exit:
        Py_XDECREF(pyVariables);
        return variables;
}

/**
 * \brief Return an array of ranges for each occurrence of the variable at an
 *        index within the scope of that variable.
 *
 * \details Call the variable_ranges() method of the Parser object. This method
 *          uses the index to determine the word at that index and finds all
 *          occurrences of it within its scope.
 *
 * \param index The index in the source string defining the scope of the parse.
 *
 * \param error On input, a pointer to a pointer for an error object. If an
 *              error occurs while getting the variable ranges, this parameter
 *              contains an error object on output unless it was NULL on input.
 *
 * \return An array of NSValue ranges where the variable is located. Return nil
 *         on error.
 */
-(NSArray *)variableRangesWithIndex:(NSUInteger)index error:(NSError **)error
{
        NSArray * variables = nil;
        PyObject * pyVariables = NULL;
        char * variablesMethod = "variable_indices";
        NSError * arrayError = nil;
        NSString * errorMessage = @"Error getting introspection variable ranges.";
        __block NSError * rangeError = nil;
        
        pyVariables = PyObject_CallMethod(pyParser, variablesMethod, "(k)", index);
        if (pyVariables == NULL) {
                if (error) {
                        *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                                     code:PLErrorCodeStatusBar
                                                 userInfo:@{NSLocalizedDescriptionKey: errorMessage,
                                                            NSLocalizedFailureReasonErrorKey: [NSString stringWithFormat:@"Could not call '%s' function", variablesMethod]}];
                }
                goto exit;
        }
        
        variables = [NSArray arrayByEnumeratingPythonSequence:pyVariables error:&arrayError withBlock:^id(PyObject * obj, NSUInteger idx) {
                NSArray * variableRange = nil;
                
                variableRange = [NSArray arrayByEnumeratingPythonSequence:obj error:&rangeError withBlock:^id(PyObject * rangeObj, NSUInteger idx) {
                        long variableRangeValue = PyLong_AsLong(rangeObj);
                        if (PyErr_Occurred()) {
                                PyErr_Clear();
                                return nil;
                        }
                        return [NSNumber numberWithLong:variableRangeValue];
                }];
                if (variableRange == nil) {
                        [[rangeError userInfo] setValue:@"Error converting Python list value to long."
                                                 forKey:NSLocalizedFailureReasonErrorKey];
                        return nil;
                }
                return [NSValue valueWithRange:NSMakeRange([[variableRange objectAtIndex:0] longValue],
                                                           [[variableRange objectAtIndex:1] longValue])];
        }];
        if (variables == nil && error) {
                *error = [NSError errorWithDomain:PLLiasisKitErrorDomain
                                             code:PLErrorCodeStatusBar
                                         userInfo:@{NSLocalizedDescriptionKey: errorMessage}];
                [[arrayError userInfo] setValue:rangeError forKey:NSUnderlyingErrorKey];
                [[*error userInfo] setValue:arrayError forKey:NSUnderlyingErrorKey];
                goto exit;
        }
        
exit:
        Py_XDECREF(pyVariables);
        return variables;
}

/**
 * \brief Get the documentation string from the parse module.
 *
 * \details Call the get_documentation() function in the parse module and
 *          convert it to an NSString object.
 *
 * \param error On input, a pointer to a pointer for an error object. If an
 *              error occurs while getting the documentation string, this
 *              parameter contains an error object on output unless it was NULL
 *              on input.
 *
 * \return A string containing the documentation for the Python source. Return
 *         nil on error.
 */
-(NSString *)getDocumentationStringAndReturnError:(NSError **)error
{
        NSString * errorMessage = nil;
        PyObject * pyDocumentation = NULL;
        char * documentation = NULL;
        char * parserMethod = "documentation";
        
        pyDocumentation = PyObject_CallMethod(pyParser, parserMethod, NULL);
        if (pyDocumentation == NULL) {
                errorMessage = [NSString stringWithFormat:@"Could not call '%s' Parser method", parserMethod];
                goto exit;
        }

        documentation = PyString_AsString(pyDocumentation);
        if (documentation == NULL) {
                errorMessage = @"Could not convert documentation to string";
                goto exit;
        }

exit:
        Py_XDECREF(pyDocumentation);
        if (error && errorMessage) {
                *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                             code:PLErrorCodeStatusBar
                                         userInfo:@{NSLocalizedDescriptionKey: @"Error getting documentation string.",
                                                    NSLocalizedFailureReasonErrorKey: errorMessage}];
        }
        if (documentation)
                return [NSString stringWithUTF8String:documentation];
        else
                return nil;
}

/**
 * \brief Get the navigation information from the parse module.
 *
 * \details This method retrieves all navigation points in Python source code.
 *          These include all function, class, and method definitions.
 *
 * \param error On input, a pointer to a pointer for an error object. If an
 *              error occurs while getting the navigation points, this parameter
 *              contains an error object on output unless it was NULL on input.
 *
 * \return A dictionary with function, class, and method ranges mapped to a
 *         `PLNavigationItem`. Return nil on error.
 */
-(NSDictionary *)getNavigationAndReturnError:(NSError **)error
{
        NSDictionary * navigation = nil;
        NSError * navigationError = nil;
        NSString * errorMessage = @"Error getting navigation information.";
        NSBundle * bundle = nil;
        PyObject * pyNavigation = NULL;
        char * parserMethod = "navigation";
        __block NSString * navigationErrorMessage;

        bundle = [NSBundle bundleForClass:[self class]];
        pyNavigation = PyObject_CallMethod(pyParser, parserMethod, NULL);
        if (pyNavigation == NULL) {
                if (error) {
                        *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                                     code:PLErrorCodeStatusBar
                                                 userInfo:@{NSLocalizedDescriptionKey: errorMessage,
                                                            NSLocalizedFailureReasonErrorKey: [NSString stringWithFormat:@"Could not call '%s' Parser method", parserMethod]}];
                }
                goto exit;
        }
        
        navigation = [NSDictionary dictionaryByEnumeratingPythonDict:pyNavigation error:&navigationError withBlock:^PLDictionaryItem *(PyObject * key, PyObject * value) {
                char * name = NULL;
                char * type = NULL;
                long lineNumber = 0;
                long length = 0;
                PyObject * pyName = NULL;
                PyObject * pyType = NULL;
                PyObject * pyLineNumber = NULL;
                PyObject * pyLength = NULL;
                PLNavigationItem * navigationItem = nil;

                pyName = PyObject_GetAttrString(value, "name");
                pyType = PyObject_GetAttrString(value, "type");
                if (pyName == NULL || pyType == NULL) {
                        navigationErrorMessage = [NSString stringWithFormat:@"Could not access navigation item object for key '%@'", key];
                        return nil;
                }
                
                name = PyString_AsString(pyName);
                type = PyString_AsString(pyType);
                if (name == NULL || type == NULL) {
                        navigationErrorMessage = [NSString stringWithFormat:@"Could not convert attributes of navigation items to C types for key '%@'", key];
                        PyErr_Clear();
                        return nil;
                }
                Py_XDECREF(pyName);
                Py_XDECREF(pyType);

                pyLineNumber = PyTuple_GetItem(key, 0);
                pyLength = PyTuple_GetItem(key, 1);
                if (pyLineNumber == NULL || pyLength == NULL) {
                        navigationErrorMessage = [NSString stringWithFormat:@"Could not unpack line range tuple for key '%@'", key];
                        PyErr_Clear();
                        return nil;
                }
                
                lineNumber = PyLong_AsLong(pyLineNumber);
                length = PyLong_AsLong(pyLength);
                if (PyErr_Occurred()) {
                        navigationErrorMessage = [NSString stringWithFormat:@"Could not convert range PyObjects to C types for key '%@'", key];
                        PyErr_Clear();
                        return nil;
                }

                navigationItem = [[[PLNavigationItem alloc] init] autorelease];
                [navigationItem setTitle:[NSString stringWithUTF8String:name]];
                [navigationItem setImage:[bundle imageForResource:[NSString stringWithUTF8String:type]]];
                
                return [PLDictionaryItem dictionaryItemWithObject:navigationItem
                                                           forKey:[NSValue valueWithRange:NSMakeRange(lineNumber, length)]];
        }];
        
        if (navigation == nil && error) {
                *error = [NSError errorWithDomain:PLLiasisErrorDomain
                                             code:PLErrorCodeStatusBar
                                         userInfo:@{NSLocalizedDescriptionKey: errorMessage,
                                                    NSUnderlyingErrorKey: navigationError}];
                if (navigationErrorMessage)
                        [[*error userInfo] setValue:navigationErrorMessage forKey:NSLocalizedFailureReasonErrorKey];
        }

exit:
        Py_XDECREF(pyNavigation);
        return navigation;
}

@end
