# -*- coding: utf-8 -*-
# vim: ts=4
###
#
# Copyright (c) 2006 Mehdi Abaakouk
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
#
###


import logging
from logging.handlers import TimedRotatingFileHandler
import subprocess
from urllib import unquote

from flask import Flask, request, abort

from toolbox import mask_is_valid, ipv6_is_valid, ipv4_is_valid, resolve

app = Flask(__name__)
app.debug = app.config["DEBUG"]
app.config.from_pyfile('lg-proxy.cfg')

file_handler = TimedRotatingFileHandler(filename=app.config["LOG_FILE"], when="midnight") 
file_handler.setLevel(getattr(logging, app.config["LOG_LEVEL"].upper()))
app.logger.addHandler(file_handler)

commands = {
    "traceroute": "traceroute %s",
    "summary": "show protocols",
    "detail": "show protocols %s all",
    "prefix": "show route for %s",
    "prefix_detail": "show route for %s all",
    "prefix_bgpmap": "show route for %s",
    "where": "show route where net ~ [ %s ]",
    "where_detail": "show route where net ~ [ %s ] all",
    "where_bgpmap": "show route where net ~ [ %s ]",
    "adv": "show route %s",
    "adv_bgpmap": "show route %s",
}

def check_accesslist():
    if  app.config["ACCESS_LIST"] and request.remote_addr not in app.config["ACCESS_LIST"]:
        abort(401)

@app.route("/traceroute")
@app.route("/traceroute6")
def traceroute():
    check_accesslist()
    
    src = []
    if request.path == '/traceroute6': 
	o = "-6"
	if app.config.get("IPV6_SOURCE",""):
	     src = [ "-s",  app.config.get("IPV6_SOURCE") ]

    else: 
	o = "-4"
	if app.config.get("IPV4_SOURCE",""):
	     src = [ "-s",  app.config.get("IPV4_SOURCE") ]

    query = request.args.get("q","")
    query = unquote(query)

    command = [ 'traceroute' , o ] + src + [ '-A', '-q1', '-N32', '-w1', '-m15', query ]
    result = subprocess.Popen( command , stdout=subprocess.PIPE).communicate()[0].decode('utf-8', 'ignore').replace("\n","<br>")
    
    return result



@app.route("/proxy")
@app.route("/proxy6")
def bird():
    check_accesslist()

    router_type = app.config.get("ROUTER_TYPE", "bird")
    if router_type == "bird":
        from bird import BirdSocket
        if request.path == "/proxy": b = BirdSocket(file="/var/run/bird.ctl")
        elif request.path == "/proxy6": b = BirdSocket(file="/var/run/bird6.ctl")
        else: return "No bird socket selected"
    else: return "Router %s is not available" % (router_type)

    cmd = request.args.get("cmd","")
    cmd = unquote(cmd)

    query = request.args.get("q","")
    query = unquote(query)

    proto = request.args.get("ip","ipv4")
    proto = unquote(proto)

    bgpmap = cmd.endswith("bgpmap")

    all = (cmd.endswith("detail") and " all" or "")
    if bgpmap:
        all = " all"

    if cmd.startswith("adv"):
        command = "show route " + query.strip()
        if bgpmap and not command.endswith("all"):
            command = command + " all"
    elif cmd.startswith("where"):
        command = "show route where net ~ [ " + query + " ]" + all
    else:
        mask = ""
        if len(query.split("/")) == 2:
            query, mask = (query.split("/"))

        if not mask and proto == "ipv4":
            mask = "32"
        if not mask and proto == "ipv6":
            mask = "128"
        if not mask_is_valid(mask):
            return error_page("mask %s is invalid" % mask)

        if proto == "ipv6" and not ipv6_is_valid(query):
            try:
                query = resolve(query, "AAAA")
            except:
                return error_page("%s is unresolvable or invalid for %s" % (query, proto))
        if proto == "ipv4" and not ipv4_is_valid(query):
            try:
                query = resolve(query, "A")
            except:
                return error_page("%s is unresolvable or invalid for %s" % (query, proto))

        if mask:
            query += "/" + mask

        command = "show route for " + query + all

    status, result = b.cmd(command)
    b.close()
    # FIXME: use status
    return result


if __name__ == "__main__":
    app.run("0.0.0.0")

