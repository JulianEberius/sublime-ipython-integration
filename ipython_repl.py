"""
For now we are using only default ipython profile and
connect to first found alive ipython kernel

We can get object info only if object is in ipython's name space

"""

import sys
# hack against IPython
sys.argv = ['']

from IPython.zmq.blockingkernelmanager import BlockingKernelManager
from json import loads
from os import listdir
from os.path import expanduser, join
import re
import socket

import sublime
import sublime_plugin


# utils


def check_port_open(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        s.shutdown(2)
        status = True
    except:
        status = False
    return status


def find_allive_server():
    # assuming we are using default profile
    security_dir = expanduser('~/.config/ipython/profile_default/security')
    all_json_files = listdir(security_dir)
    for json_file in all_json_files:
        with open(join(security_dir, json_file)) as f:
            cfg = loads(f.read())
        ip, port = cfg['ip'], cfg['shell_port']
        if check_port_open(ip, port):
            return cfg


# text processing

def strip_comment_lines(s):
    comment = re.compile('^#.+')
    return comment.sub('', s)


def strip_color_escapes(s):
    strip = re.compile('\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]')
    return strip.sub('', s)


# initialize kernel functions

def km_from_cfg(cfg):
    km = BlockingKernelManager(**cfg)
    km.shell_channel.start()
    km.shell_channel.session.key = km.key
    return km


def initialize_km():
    cfg = find_allive_server()
    if not cfg:
        return
    return km_from_cfg(cfg)


def get_response(km, msg_id):
    msgs = km.shell_channel.get_msgs()
    while not msgs:
        msgs = km.shell_channel.get_msgs()
    return [m for m in msgs
            if m['parent_header']['msg_id'] == msg_id]


def execute_code(km, code):
    code = strip_comment_lines(code)
    km.shell_channel.execute(code)


# magic object info

def get_object_info(km, word):
    msg_id = km.shell_channel.object_info(word)
    response = get_response(km, msg_id)
    return response[0]


class IpythonExecCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sel = self.view.sel()
        if sel[0]:
            text = '\n'.join(self.view.substr(reg) for reg in sel)
        else:
            size = self.view.size()
            text = self.view.substr(sublime.Region(0, size))
        km = initialize_km()
        execute_code(km, text)
        return []


class IpythonMagicInfoCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sel = self.view.sel()
        if not sel[0]:
            return []
        text = self.view.substr(sel[0])
        km = initialize_km()
        info = get_object_info(km, text)
        if info:
            self.output(info['content']['docstring'])
        return []

    def output(self, string):
        out_view = self.view.window().get_output_panel("ipython_object_info")
        # out_view.settings().set("syntax", "Packages/Python/Python.tmLanguage")
        r = sublime.Region(0, out_view.size())
        e = out_view.begin_edit()
        out_view.erase(e, r)
        out_view.insert(e, 0, string)
        out_view.end_edit(e)
        out_view.show(0)
        self.view.window().run_command(
            "show_panel", {"panel": "output.ipython_object_info"})
        self.view.window().focus_view(out_view)

