#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import os
import platform
import shlex
import subprocess
import sys

import sipconfig

from distutils.core import DistutilsError
from distutils.ccompiler import CCompiler
from distutils.sysconfig import customize_compiler
from os.path import join, exists, abspath, dirname

from setuptools import setup, Extension

from sipdistutils import build_ext

from PyQt5.QtCore import PYQT_CONFIGURATION
from PyQt5.QtCore import QLibraryInfo


def get_git_build_number():
    TAG = "UNKNOWN"
    exe_extension = ".exe" if (sys.platform == "win32") else ""
    exe_name = "git{0}".format(exe_extension)

    TAG = DISTANCE = COMMIT = DATE = MODIFIED = None

    command = shlex.split(u"{0} describe --tags --always".format(exe_name))
    pipe = subprocess.run(command, stdout=subprocess.PIPE, check=True, shell=False)
    for line in pipe.stdout.split(b'\n'):
        parts = line.strip().split(b'-')
        COMMIT = parts[-1].replace(b'g', b'').decode('utf8')
        DISTANCE = int(parts[-2])
        TAG = b'-'.join(parts[:-2]).decode('utf8')
        break

    command = shlex.split(u"{0} status --porcelain -uno".format(exe_name))
    pipe = subprocess.run(command, stdout=subprocess.PIPE, check=True, shell=False)
    MODIFIED = True if len(pipe.stdout) else False

    command = shlex.split(u"{0} show -s --format=%cI".format(exe_name))
    pipe = subprocess.run(command, stdout=subprocess.PIPE, check=True, shell=False)
    for line in pipe.stdout.split(b'\n'):
        line = line.strip().decode('ascii')
        # Something like '2019-06-20T09:04:10+02:00'
        # Python 3.5 %z strptime format does not like the ':' in TZ
        date_part, tz_part = line.split('+')
        line = '+'.join((date_part, tz_part.replace(':', '')))
        DATE = datetime.datetime.strptime(line, "%Y-%m-%dT%H:%M:%S%z")
        break

    return TAG, DISTANCE, COMMIT, DATE, MODIFIED

# monkey-patch for parallel compilation, see
# https://stackoverflow.com/questions/11013851/speeding-up-build-process-with-distutils
def parallelCCompile(self, sources, output_dir=None, macros=None, include_dirs=None, debug=0, extra_preargs=None, extra_postargs=None, depends=None):
    # those lines are copied from distutils.ccompiler.CCompiler directly
    macros, objects, extra_postargs, pp_opts, build = self._setup_compile(output_dir, macros, include_dirs, sources, depends, extra_postargs)
    cc_args = self._get_cc_args(pp_opts, debug, extra_preargs)
    # parallel code
    N = os.cpu_count() # number of parallel compilations
    import multiprocessing.pool
    def _single_compile(obj):
        try: src, ext = build[obj]
        except KeyError: return
        self._compile(obj, src, ext, cc_args, extra_postargs, pp_opts)
    # convert to list, imap is evaluated on-demand
    list(multiprocessing.pool.ThreadPool(N).imap(_single_compile,objects))
    return objects


WINDOWS_HOST = (platform.system() == 'Windows')
LINUX_HOST = (platform.system() == 'Linux')

# This is with Unix pathsep even on windows
QT_BINARIES = QLibraryInfo.location(QLibraryInfo.BinariesPath)
if WINDOWS_HOST:
    # Default to MSVC nmake
    DEFAULT_MAKE = 'jom.exe'
    DEFAULT_QMAKE = "{}/{}".format(QT_BINARIES, "qmake.exe")
else:
    DEFAULT_MAKE = 'make'
    DEFAULT_QMAKE = "{}/{}".format(QT_BINARIES, "qmake")

DEFAULT_QT_INCLUDE = QLibraryInfo.location(QLibraryInfo.HeadersPath)
ROOT = abspath(dirname(__file__))
BUILD_STATIC_DIR = join(ROOT, 'lib-static')

# Monkey-patch, see above
CCompiler.compile=parallelCCompile


class MyBuilderExt(build_ext):
    user_options = build_ext.user_options[:]
    user_options += [
        ('qmake=', None, 'Path to qmake'),
        ('qt-include-dir=', None, 'Path to Qt headers'),
        ('qt-library-dir=', None, 'Path to Qt library dir (used at link time)'),
        ('make=', None, 'Path to make (either GNU make/nmake/jom)')
    ]

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.qmake = None
        self.qt_include_dir = None
        self.qt_library_dir = None
        self.make = None
        self.static_lib = None
        pyqt_sip_config = PYQT_CONFIGURATION['sip_flags']
        if self.sip_opts is None:
            self.sip_opts = pyqt_sip_config
        else:
            self.sip_opts += pyqt_sip_config

    def finalize_options(self):
        build_ext.finalize_options(self)
        if self.qmake is None:
            print('Setting qmake to \'%s\'' % DEFAULT_QMAKE)
            self.qmake = DEFAULT_QMAKE
        if self.make is None:
            print('Setting make to \'%s\'' % DEFAULT_MAKE)
            self.make = DEFAULT_MAKE
        if self.qt_include_dir is None:
            pipe = subprocess.Popen([self.qmake, "-query", "QT_INSTALL_HEADERS"], stdout=subprocess.PIPE)
            (stdout, stderr) = pipe.communicate()
            self.qt_include_dir = str(stdout.strip(), 'utf8')
            print('Setting Qt include dir to \'%s\'' % self.qt_include_dir)

        if self.qt_library_dir is None:
            pipe = subprocess.Popen([self.qmake, "-query", "QT_INSTALL_LIBS"], stdout=subprocess.PIPE)
            (stdout, stderr) = pipe.communicate()
            self.qt_library_dir = str(stdout.strip(), 'utf8')
            print('Setting Qt library dir to \'%s\'' % self.qt_library_dir)

        if not exists(self.qmake):
            raise DistutilsError('Could not determine valid qmake at %s' % self.qmake)

    def __build_qcustomplot_library(self):
        if WINDOWS_HOST:
            qcustomplot_static = join(self.build_temp, 'release', 'qcustomplot.lib')
        else:
            qcustomplot_static = join(self.build_temp, 'libqcustomplot.a')
        if exists(qcustomplot_static):
            return

        os.makedirs(self.build_temp, exist_ok=True)
        os.chdir(self.build_temp)
        print('Make static qcustomplot library...')
        self.spawn([self.qmake, join(ROOT, 'QCustomPlot/src/qcp-staticlib.pro')])
        # AFAIK only nmake does not support -j option
        has_multiprocess = not(WINDOWS_HOST and "nmake" in self.make)
        make_cmdline = [self.make]
        if has_multiprocess:
            make_cmdline.extend(('-j', str(os.cpu_count())))
        make_cmdline.append('release')
        self.spawn(make_cmdline)

        os.chdir(ROOT)
        self.static_lib = qcustomplot_static
        # Possibly it's hack
        qcustomplot_ext = self.extensions[0]
        qcustomplot_ext.extra_objects = [qcustomplot_static]

    def build_extensions(self):
        customize_compiler(self.compiler)
        try:
            self.compiler.compiler_so.remove('-Wstrict-prototypes')
        except (AttributeError, ValueError):
            pass
        self.__build_qcustomplot_library()
        # Possibly it's hack
        qcustomplot_ext = self.extensions[0]
        qcustomplot_ext.include_dirs += [
            join(self.qt_include_dir, subdir)
            for subdir in ['.', 'QtCore', 'QtGui', 'QtWidgets', 'QtPrintSupport']
        ]
        qcustomplot_ext.library_dirs += [
            self.build_temp,
            self.qt_library_dir
        ]

        qcustomplot_ext.libraries = [
            'qcustomplot',
            'Qt5Core',
            'Qt5Gui',
            'Qt5Widgets',
            # For some unknown reason GCC 9.2.1 20191102 on Debian does not link Qt5PrintSupport
            # if -lqcustomplot comes in last
            'Qt5PrintSupport'
        ]

        if WINDOWS_HOST:
            qcustomplot_ext.extra_compile_args.append("/Zi")
            qcustomplot_ext.extra_link_args.append("/DEBUG:FULL")
            qcustomplot_ext.library_dirs.append(join(self.build_temp, 'release'))
            qcustomplot_ext.libraries.append('Opengl32')

        build_ext.build_extensions(self)

    def _sip_sipfiles_dir(self):
        cfg = sipconfig.Configuration()
        return join(cfg.default_sip_dir, 'PyQt5')


TAG, DISTANCE, COMMIT, DATE, MODIFIED = get_git_build_number()

if not DISTANCE:
    # We're on a tag, good
    version = TAG
else:
    # Revert to year.month.dev{distance}+{commit}
    version = "{0.year}.{0.month}.dev{1}+{2}".format(DATE, DISTANCE, COMMIT)

setup(
    name='QCustomPlot',
    version=version,
    description='QCustomPlot is a PyQt5 widget for plotting and data visualization',
    author='Dmitry Voronin, Giuseppe Corbelli',
    author_email='carriingfate92@yandex.ru',
    url='https://github.com/dimv36/QCustomPlot-PyQt5',
    platforms=['Linux'],
    license='MIT',
    ext_modules=[
        Extension(
            'QCustomPlot',
            ['all.sip'],
            include_dirs=['.']
        ),
    ],
    requires=[
        'sipconfig',
        'PyQt5'
    ],
    cmdclass={'build_ext': MyBuilderExt}
)
