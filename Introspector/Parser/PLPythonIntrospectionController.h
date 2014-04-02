/**
 * \file PLPythonIntrospectionController.h
 * \brief Liasis Python IDE text editor code parser.
 *
 * \details This file contains the public interface for the code introspection
 * parser. This class provides methods for parsing and providing information
 * about a Python file.
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

#import <Foundation/Foundation.h>
#import <Python/Python.h>
#import <LiasisKit/LiasisKit.h>

/**
 * \class PLPythonIntrospectionController \headerfile \headerfile
 *
 * \brief Interoperate with a Python module to provide introspection into Python
 *        source code.
 *
 * \details This class provides methods for parsing Python source code and
 *          returning information about the source, including an array of
 *          variables defined at a particular scope, documentation for all
 *          functions and classes in the file, and nestable lines.
 */
@interface PLPythonIntrospectionController : NSObject <PLAddOnPluginIntrospection> {
        /**
         * \brief The Python Parser object responsible for parsing source code.
         */
        PyObject * pyParser;
}

/**
 * \brief Initialize the introspection controller.
 *
 * \details Update the python path to find the parse module in the plugin
 *          bundle. Import the parse module and create a Parser object, assiging
 *          it to the pyParser instance variable. Returns nil if there was an
 *          error interfacing with Python.
 *
 * \return The Python introspection controller.
 */
-(id)init;

@end