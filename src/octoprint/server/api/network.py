import logging
import subprocess
import netaddr

from flask import Blueprint, request, jsonify, abort, current_app, session, make_response
from flask.ext.login import login_user, logout_user, current_user
from flask.ext.principal import Identity, identity_changed, AnonymousIdentity

import octoprint.util as util
import octoprint.users
import octoprint.server
from octoprint.server import restricted_access, admin_permission, NO_CONTENT
from octoprint.server.api import api
from octoprint.settings import settings as s, valid_boolean_trues

#~~ network setup
@api.route("/netsettings", methods=["GET"])
@restricted_access
@admin_permission.require(403)
def getNetworkSettings():
    wifiInterface = octoprint.server.wifiInterface
    wifiManager = octoprint.server.wifiManager

    netSettings = wifiManager.getSettings(wifiInterface)

    return jsonify({
        "networkSettings": netSettings
    }) 

@api.route("/needsWifiChange", methods=["POST"])
@restricted_access
@admin_permission.require(403)
def needsWifiChange():
    logger = logging.getLogger(__name__)
    logger.info("needsWifiChange() called")

    requestData = None
    if "application/json" in request.headers["Content-Type"]:
        requestData = request.json

    wifiInterface = octoprint.server.wifiInterface
    wifiManager = octoprint.server.wifiManager
    wifiNeedsChangeResult = wifiManager.needsSettingsChange(wifiInterface, requestData)

    return jsonify({
        'wifiNeedsChangeResult': wifiNeedsChangeResult
    })

@api.route("/setWifiSettings", methods=["POST"])
@restricted_access
@admin_permission.require(403)
def setWifiSettings():
    logger = logging.getLogger(__name__)
    logger.info("setWifiSettings() called")

    requestData = None
    if "application/json" in request.headers["Content-Type"]:
        requestData = request.json

    wifiInterface = octoprint.server.wifiInterface
    wifiManager = octoprint.server.wifiManager
    wifiSettingsChangeResult = wifiManager.setSettings(wifiInterface, requestData)

    return jsonify({
        "wifiSettingsChangeResult": wifiSettingsChangeResult,
    })
