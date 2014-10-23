function SettingsViewModel(loginStateViewModel, usersViewModel) {
    var self = this;

    self.loginState = loginStateViewModel;
    self.users = usersViewModel;

	// TYPEA: initialize our container for all the stuff necessary to handle network settings.
	self.netSettings = new NetSettings(self);

    self.api_enabled = ko.observable(undefined);
    self.api_key = ko.observable(undefined);

    self.appearance_name = ko.observable(undefined);
    self.appearance_color = ko.observable(undefined);

    self.appearance_available_colors = ko.observable(["default", "red", "orange", "yellow", "green", "blue", "violet", "black"]);

    self.printer_movementSpeedX = ko.observable(undefined);
    self.printer_movementSpeedY = ko.observable(undefined);
    self.printer_movementSpeedZ = ko.observable(undefined);
    self.printer_movementSpeedE = ko.observable(undefined);
    self.printer_invertAxes = ko.observable(undefined);
    self.printer_numExtruders = ko.observable(undefined);

    self._printer_extruderOffsets = ko.observableArray([]);
    self.printer_extruderOffsets = ko.computed({
        read: function() {
            var extruderOffsets = self._printer_extruderOffsets();
            var result = [];
            for (var i = 0; i < extruderOffsets.length; i++) {
                result[i] = {
                    x: parseFloat(extruderOffsets[i].x()),
                    y: parseFloat(extruderOffsets[i].y())
                }
            }
            return result;
        },
        write: function(value) {
            var result = [];
            if (value && Array.isArray(value)) {
                for (var i = 0; i < value.length; i++) {
                    result[i] = {
                        x: ko.observable(value[i].x),
                        y: ko.observable(value[i].y)
                    }
                }
            }
            self._printer_extruderOffsets(result);
        },
        owner: self
    });
    self.ko_printer_extruderOffsets = ko.computed(function() {
        var extruderOffsets = self._printer_extruderOffsets();
        var numExtruders = self.printer_numExtruders();
        if (!numExtruders) {
            numExtruders = 1;
        }

        if (numExtruders > extruderOffsets.length) {
            for (var i = extruderOffsets.length; i < numExtruders; i++) {
                extruderOffsets[i] = {
                    x: ko.observable(0),
                    y: ko.observable(0)
                }
            }
            self._printer_extruderOffsets(extruderOffsets);
        }

        return extruderOffsets.slice(0, numExtruders);
    });

    self.printer_bedDimensionX = ko.observable(undefined);
    self.printer_bedDimensionY = ko.observable(undefined);
    self.printer_bedDimensions = ko.computed({
        read: function () {
            return {
                x: parseFloat(self.printer_bedDimensionX()),
                y: parseFloat(self.printer_bedDimensionY())
            };
        },
        write: function(value) {
            self.printer_bedDimensionX(value.x);
            self.printer_bedDimensionY(value.y);
        },
        owner: self
    });

    self.webcam_streamUrl = ko.observable(undefined);
    self.webcam_snapshotUrl = ko.observable(undefined);
    self.webcam_ffmpegPath = ko.observable(undefined);
    self.webcam_bitrate = ko.observable(undefined);
    self.webcam_watermark = ko.observable(undefined);
    self.webcam_flipH = ko.observable(undefined);
    self.webcam_flipV = ko.observable(undefined);

    self.feature_gcodeViewer = ko.observable(undefined);
    self.feature_temperatureGraph = ko.observable(undefined);
    self.feature_waitForStart = ko.observable(undefined);
    self.feature_alwaysSendChecksum = ko.observable(undefined);
    self.feature_sdSupport = ko.observable(undefined);
    self.feature_sdAlwaysAvailable = ko.observable(undefined);
    self.feature_swallowOkAfterResend = ko.observable(undefined);
    self.feature_networkSettings = ko.observable(undefined);
    self.feature_repetierTargetTemp = ko.observable(undefined);

    self.serial_port = ko.observable();
    self.serial_baudrate = ko.observable();
    self.serial_portOptions = ko.observableArray([]);
    self.serial_baudrateOptions = ko.observableArray([]);
    self.serial_autoconnect = ko.observable(undefined);
    self.serial_timeoutConnection = ko.observable(undefined);
    self.serial_timeoutDetection = ko.observable(undefined);
    self.serial_timeoutCommunication = ko.observable(undefined);
    self.serial_timeoutTemperature = ko.observable(undefined);
    self.serial_timeoutSdStatus = ko.observable(undefined);
    self.serial_log = ko.observable(undefined);

    self.folder_uploads = ko.observable(undefined);
    self.folder_timelapse = ko.observable(undefined);
    self.folder_timelapseTmp = ko.observable(undefined);
    self.folder_logs = ko.observable(undefined);

    self.cura_enabled = ko.observable(undefined);
    self.cura_path = ko.observable(undefined);
    self.cura_config = ko.observable(undefined);

    self.temperature_profiles = ko.observableArray(undefined);

    self.system_actions = ko.observableArray([]);

    self.terminalFilters = ko.observableArray([]);

    self.addTemperatureProfile = function() {
        self.temperature_profiles.push({name: "New", extruder:0, bed:0});
    };

    self.removeTemperatureProfile = function(profile) {
        self.temperature_profiles.remove(profile);
    };

    self.addTerminalFilter = function() {
        self.terminalFilters.push({name: "New", regex: "(Send: M105)|(Recv: ok T:)"})
    };

    self.removeTerminalFilter = function(filter) {
        self.terminalFilters.remove(filter);
    };

    self.getPrinterInvertAxis = function(axis) {
        return _.contains((self.printer_invertAxes() || []), axis.toLowerCase());
    };

    self.setPrinterInvertAxis = function(axis, value) {
        var currInvert = self.printer_invertAxes() || [];
        var currValue = self.getPrinterInvertAxis(axis);
        if (value && !currValue) {
            currInvert.push(axis.toLowerCase());
        } else if (!value && currValue) {
            currInvert = _.without(currInvert, axis.toLowerCase());
        }
        self.printer_invertAxes(currInvert);
    };

    self.koInvertAxis = function (axis) { return ko.computed({
        read: function () { return self.getPrinterInvertAxis(axis); },
        write: function (value) { self.setPrinterInvertAxis(axis, value); },
        owner: self
    })};

    self.printer_invertX = self.koInvertAxis('x');
    self.printer_invertY = self.koInvertAxis('y');
    self.printer_invertZ = self.koInvertAxis('z');

    self.requestData = function(callback) {
        $.ajax({
            url: API_BASEURL + "settings",
            type: "GET",
            dataType: "json",
            success: function(response) {
                self.fromResponse(response);
                if (callback) callback();
            }
        });
    };

    self.fromResponse = function(response) {
        self.api_enabled(response.api.enabled);
        self.api_key(response.api.key);

        self.appearance_name(response.appearance.name);
        self.appearance_color(response.appearance.color);

        self.printer_movementSpeedX(response.printer.movementSpeedX);
        self.printer_movementSpeedY(response.printer.movementSpeedY);
        self.printer_movementSpeedZ(response.printer.movementSpeedZ);
        self.printer_movementSpeedE(response.printer.movementSpeedE);
        self.printer_invertAxes(response.printer.invertAxes);
        self.printer_numExtruders(response.printer.numExtruders);
        self.printer_extruderOffsets(response.printer.extruderOffsets);
        self.printer_bedDimensions(response.printer.bedDimensions);

        self.webcam_streamUrl(response.webcam.streamUrl);
        self.webcam_snapshotUrl(response.webcam.snapshotUrl);
        self.webcam_ffmpegPath(response.webcam.ffmpegPath);
        self.webcam_bitrate(response.webcam.bitrate);
        self.webcam_watermark(response.webcam.watermark);
        self.webcam_flipH(response.webcam.flipH);
        self.webcam_flipV(response.webcam.flipV);

        self.feature_gcodeViewer(response.feature.gcodeViewer);
        self.feature_temperatureGraph(response.feature.temperatureGraph);
        self.feature_waitForStart(response.feature.waitForStart);
        self.feature_alwaysSendChecksum(response.feature.alwaysSendChecksum);
        self.feature_sdSupport(response.feature.sdSupport);
        self.feature_sdAlwaysAvailable(response.feature.sdAlwaysAvailable);
		self.feature_networkSettings(response.feature.networkSettings);
        self.feature_swallowOkAfterResend(response.feature.swallowOkAfterResend);
        self.feature_repetierTargetTemp(response.feature.repetierTargetTemp);

        self.serial_port(response.serial.port);
        self.serial_baudrate(response.serial.baudrate);
        self.serial_portOptions(response.serial.portOptions);
        self.serial_baudrateOptions(response.serial.baudrateOptions);
        self.serial_autoconnect(response.serial.autoconnect);
        self.serial_timeoutConnection(response.serial.timeoutConnection);
        self.serial_timeoutDetection(response.serial.timeoutDetection);
        self.serial_timeoutCommunication(response.serial.timeoutCommunication);
        self.serial_timeoutTemperature(response.serial.timeoutTemperature);
        self.serial_timeoutSdStatus(response.serial.timeoutSdStatus);
        self.serial_log(response.serial.log);

        self.folder_uploads(response.folder.uploads);
        self.folder_timelapse(response.folder.timelapse);
        self.folder_timelapseTmp(response.folder.timelapseTmp);
        self.folder_logs(response.folder.logs);

        self.cura_enabled(response.cura.enabled);
        self.cura_path(response.cura.path);
        self.cura_config(response.cura.config);

        self.temperature_profiles(response.temperature.profiles);

        self.system_actions(response.system.actions);

        self.terminalFilters(response.terminalFilters);
    };

	// TYPEA: FIXME: why do the net settings observables break if we move them to NetSettings()? I've tried qualifing
	// their data binds with "netSettings." to no avail.

	// TYPEA: these are bogus observables that are used initialize the Selectize widget's data bind. Selectize elements
	// don't load properly if they don't have the data-bind set. But data-binding selectize elements doesn't actually
	// work with ko2. So, we pass these two empty values to the selectize data-bind in the HTML, and then fill in real
	// options later, in the NetSettings.updateUI() function.
	self.selectizeValue = ko.observable(0);
	self.selectizeValues = ko.observableArray([{id:0, name:"none"}]);

    self.wifi_passkey = ko.observable("");

	// TYPEA: flag to indicate if the settings were saved. Used by the network settings code below to indicate if the
	// user saved the settings (instead of canceling the settings dialog). Set to true in self.saveData() and then set
	// back to false after the settings dialog is hidden.
	self.settingsSaved = false;
	
	// TYPEA: flag to make sure we don't reinstall the settings dialog event handlers.
	self.settingsDialogEventHandlersInstalled = false;

	if (!self.settingsDialogEventHandlersInstalled)
	{
		// TYPEA: install an event handler to to tell the network settings that the settings dialog is about to be
		// shown..
		$('#settings_dialog').on('show', function() {
			self.settingsSaved = false;
			self.netSettings.settingsDialogWillShow();
		});

		// TYPEA: install an event handler to to tell the network settings to save (see below) and also to reset the
		// settingsSaved flag after the settings dialog is hidden.
		$('#settings_dialog').on('hidden', function() {
			console.log("NetSettings: handling settings dialog hidden event.");
			self.netSettings.settingsDialogDidHide(self.settingsSaved);
		});
	}

    self.saveData = function() {
		self.settingsSaved = true;

        var data = {
            "api" : {
                "enabled": self.api_enabled(),
                "key": self.api_key()
            },
            "appearance" : {
                "name": self.appearance_name(),
                "color": self.appearance_color()
            },
            "printer": {
                "movementSpeedX": self.printer_movementSpeedX(),
                "movementSpeedY": self.printer_movementSpeedY(),
                "movementSpeedZ": self.printer_movementSpeedZ(),
                "movementSpeedE": self.printer_movementSpeedE(),
                "invertAxes": self.printer_invertAxes(),
                "numExtruders": self.printer_numExtruders(),
                "extruderOffsets": self.printer_extruderOffsets(),
                "bedDimensions": self.printer_bedDimensions()
            },
            "webcam": {
                "streamUrl": self.webcam_streamUrl(),
                "snapshotUrl": self.webcam_snapshotUrl(),
                "ffmpegPath": self.webcam_ffmpegPath(),
                "bitrate": self.webcam_bitrate(),
                "watermark": self.webcam_watermark(),
                "flipH": self.webcam_flipH(),
                "flipV": self.webcam_flipV()
            },
            "feature": {
                "gcodeViewer": self.feature_gcodeViewer(),
                "temperatureGraph": self.feature_temperatureGraph(),
                "waitForStart": self.feature_waitForStart(),
                "alwaysSendChecksum": self.feature_alwaysSendChecksum(),
                "sdSupport": self.feature_sdSupport(),
                "sdAlwaysAvailable": self.feature_sdAlwaysAvailable(),
				"networkSettings": self.feature_networkSettings(),
                "swallowOkAfterResend": self.feature_swallowOkAfterResend(),
                "repetierTargetTemp": self.feature_repetierTargetTemp()
            },
            "serial": {
                "port": self.serial_port(),
                "baudrate": self.serial_baudrate(),
                "autoconnect": self.serial_autoconnect(),
                "timeoutConnection": self.serial_timeoutConnection(),
                "timeoutDetection": self.serial_timeoutDetection(),
                "timeoutCommunication": self.serial_timeoutCommunication(),
                "timeoutTemperature": self.serial_timeoutTemperature(),
                "timeoutSdStatus": self.serial_timeoutSdStatus(),
                "log": self.serial_log()
            },
            "folder": {
                "uploads": self.folder_uploads(),
                "timelapse": self.folder_timelapse(),
                "timelapseTmp": self.folder_timelapseTmp(),
                "logs": self.folder_logs()
            },
            "temperature": {
                "profiles": self.temperature_profiles()
            },
            "system": {
                "actions": self.system_actions()
            },
            "cura": {
                "enabled": self.cura_enabled(),
                "path": self.cura_path(),
                "config": self.cura_config()
            },
            "terminalFilters": self.terminalFilters()
        };

        $.ajax({
            url: API_BASEURL + "settings",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify(data),
            success: function(response) {
                self.fromResponse(response);
                $("#settings_dialog").modal("hide");
            }
        });
    }
}


// TYPEA: NetSettings is a container for all the stuff necessary to handle network settings, so that we keep from
// crowding the view model with a zillion new non-persistable variables.
function NetSettings(settingsViewModel)
{
    var self = this;

	console.log("NetSettings() called.");

	// TYEPA: set up networking settings. The wifi configuration settings (and right now, these are the only network
	// settings) circumvent ko and the get/set settings requests because they aren't actually stored as Octoprint
	// settings. Instead, they'll be written out to the device network interfaces config file by the server. Thus, we
	// populate the wifi settings UI using special requests and then post them to the server when the settings dialog is
	// dismissed.
	//
	// This process is fairly elaborate. One of the problems with switching the network interface of the Beagle on the
	// fly is that it's very, very slow and thus ties up the server when it happens. Thus, we need to put up a modal
	// to inform the user that it's going to take a while (and prevent further user interactions, since the server is
	// is going to busy with ifup/ifdown). To make that work, we go through the following steps:
	//
	//	1.	During the Settings dialog hidden handler, we POST the current wifi UI values to the server. The server
	//		response indicates if these values will cause the Beagle to change its net config. If the server says the
	//		settings haven't changed, we're done.
	//	2.	If the server says our settings will change the Beagle's config, then we put a modal alert telling the user
	//		what's happening and that it's going to be slow. This modal has no close UI and locks out all user
	//		interaction with Octoprint.
	//	3.	From the modal alert's shown handle, we POST a request to the server to actually change the wifi settings to
	//		the new values the user has entered. The server's response indicates whether that operation succeeded and
	//		why it failed, if it did.
	//	4.	The POST handler from step 3 hides the modal alert and informs the user whether the wifi settings change was
	//		was successful.
	//
	// Also, note that we use Selectize to implement a nice combobox UI not available from ko or bootstrap and it
	// doesn't really play nice with ko2. Thus, some of the ick in NetSettings is there for directly interfacing with
	// Selectize. If Octoprint ever transitions to ko3, this could be cleaned up.

	self.settingsViewModel = settingsViewModel;

	// TYPEA: flag to indicate the UI has been updated. This is necessary because we don't update the UI until the 
	// Network Settings tab is shown. Thus, we need a flag to indicate that has happened so we don't re-initialize the
	// UI if the user switches to another tab and back again. The uiUpdated flag gets cleared by our cleanupUI function,
	// which is called when the settings dialog is dismissed
	self.uiUpdated = false;

	// TYPEA: flag to indicate the UI has been fully initialized.
	self.uiInitialized = false;

	// TYPEA: guard flag to insure we don't install event handler callbacks on the alert dialog more than once. 
	self.wifiAlertEventHandlersInstalled = false;
	
	// TYPEA: guard flag to insure we don't install event handler callbacks on the enable wifi checkbox more than once. 
	self.wifiEnableWifiCBoxEventHandlersInstalled = false;
	
	// TYPEA: guard flag to insure we don't install event handler callbacks on the enable wifi alert more than once. 
	self.wifiEnableAlertEventHandlersInstalled = false;

	// TYPEA: interface to Selectize direct API. This gets set by the selectize custom ko binding in main.js. Weirdly,
	// it seems Selectize's direct interface object can be accessed exactly once. The custom ko binding gets it first,
	// so it propagates it to us using this instance variable.
	self.selectize = null;

	// TYPEA: initialization options for Selectize.
	self.selectizeInitOptions = {
		theme: 'selectize-dropdown [data-selectable]',
		valueField: "id",
		labelField: "name",
		searchField: ["name"],
		sortField: "id",
		options: [],
		maxItems: 1,
		create: true,
		persist: true
	};

	// TYPEA: the array of visible SSIDs, according to the server. 
	self.visibleSSIDs = [];

	self.settingsDialogWillShow = function() {
		self.updateUI();
	}

	self.settingsDialogDidHide = function(saveSettings) {
		self.tryToSave(saveSettings);
		self.resetUI();
		self.reset();
	}

	self.updateUI = function() {
 		console.log("updating network settings UI: " + !self.uiUpdated + ".");
 		
 		// TYPEA: if we've already set the network settings UI for the current invocation of the Settings dialog, then
 		// bail.
 		if (self.uiUpdated)
  			return;
 
 		if (!self.wifiEnableWifiCBoxEventHandlersInstalled) {
			 $('#settings-wifienabled').change(function() {
			 	self.wifiEnabledCBoxDidChange($(this).is(':checked'));
			});
			
			self.wifiEnableWifiCBoxEventHandlersInstalled = true;
		}
 
		console.log("SettingsViewModel Selectize interface: ");
		console.log(self.selectize);

		// TYPEA: ask the server for the Beagle's current network config.
		$.ajax({
			url: API_BASEURL + "netsettings",
			type: "GET",
            cache: false,
			dataType: "json",
			success: function(response) {
				console.log("received network settings for network settings tab.")
				console.log(response);
				self.initUI(response);
			}
		});

		self.uiUpdated = true;
 	}

	self.disableUI = function() {
		$("#settings-wifienabled").prop("disabled", true);
		self.selectize.disable();
		$("#settings-wifipasskey").prop("disabled", true);
	}

	self.refreshUI = function() {
		self.uiUpdated = false;
		self.uiInitialized = false;
		
		self.updateUI();
	}

	self.initUI = function(response) {
		console.log("self.initUI(): response from get settings request:")
		console.log(response)

		if (!"networkSettings" in response) {
			self.disableUI();
			return;
		}

		var netSettings = response.networkSettings;		
		if ("wifiPasskey" in netSettings) {
			self.settingsViewModel.wifi_passkey(netSettings.wifiPasskey);
		}

		var enabled = false;
		if ("wifiEnabled" in netSettings) {
			enabled = netSettings.wifiEnabled;
		}

		$("#settings-wifienabled").prop("checked", enabled);

		if (!enabled) {
			self.selectize.disable();
			$("#settings-wifipasskey").prop("disabled", true);
		}

		self.visibleSSIDs.length = 0;
		if ("wifiVisibleSSIDs" in netSettings) {
			self.visibleSSIDs = netSettings.wifiVisibleSSIDs;
		}

		var selectedSSID = "";
		if ("wifiSelectedSSID" in netSettings)
			selectedSSID = netSettings.wifiSelectedSSID;

		var noneSelected = false;
		if ("wifiNoneSelected" in netSettings) {
			noneSelected = netSettings.wifiNoneSelected;
		} else {
			noneSelected = (selectedSSID.length <= 0);
		}

		self.selectize.clearOptions();

		var selectedCellID = 0
		var visibleSSIDCount = self.visibleSSIDs.length;
		if (visibleSSIDCount > 0) {
			var noneOption = { id:0, name:"(none selected)" };
			self.selectize.addOption(noneOption);
	
			var index = 0;
			for (index = 0; index < visibleSSIDCount; ++index) {
				var ssid = self.visibleSSIDs[index];
				self.selectize.addOption(ssid);
				if (ssid.name == selectedSSID && !noneSelected) {
					selectedCellID = ssid.id;
				}
			}
		} else {
			var noneOption = {};
			if (enabled)
				noneOption = { id:0, name:"(no wifi networks detected)" };
			else
				noneOption = { id:0, name:"(wifi turned off)" };

			self.selectize.addOption(noneOption);
		}

		if ((selectedCellID == 0) && (selectedSSID.length > 0))
		{
			var invisibleOption = { id:-1, name:selectedSSID };
			self.selectize.addOption(invisibleOption);
			selectedCellID = -1
		}

		self.selectize.setValue(selectedCellID);
		self.selectize.refreshOptions(false);
		
		self.uiInitialized = true;		
	}

 	self.resetUI = function() {	
		// TYPEA: set our updated flag to false so we'll know to refresh the next time we're shown.
		self.uiUpdated = false;
		self.uiInitialized = false;
 	}
 
 	self.reset = function()
 	{
		self.settingsSaved = false;
 		if (self.visibleSSID)
 			self.visibleSSIDs.length = 0;
 	}

 	self.tryToSave = function(saveSettings) {
 		console.log("NetSettings.tryToSave() called.");

		if (!saveSettings)
 			// TYPEA: don't do anyting if the user canceled the settings dialog.
 			return;
 
  		console.log("NetSettings.tryToSave() attempting to save.");

 		var selectedSSID = "";
 		var noneSelected = false;
 
		var selectedID = parseInt(self.selectize.getValue());
		if (selectedID != 0) {
			var visibleSSIDCount = self.visibleSSIDs.length;
			var index = 0;
			for (index = 0; index < visibleSSIDCount; ++index) {
				var ssid = self.visibleSSIDs[index];
				if (selectedID == ssid.id) {
					selectedSSID = ssid.name;
				}
			}
		} else {
			noneSelected = true;
		}

		console.log("NetSettings.tryToSave(): selectedSSID: " + selectedSSID + ", wifiPasskey: " + self.settingsViewModel.wifi_passkey());
		console.log("NetSettings.tryToSave(): wifi enabled: " + $("#settings-wifienabled").is(':checked'));

		self.wifiUIState = {
			'wifiEnabled': $("#settings-wifienabled").is(':checked'),
			'wifiSelectedSSID': selectedSSID,
			'wifiPasskey': self.settingsViewModel.wifi_passkey(),
			'wifiNoneSelected': noneSelected
		};
		
        var postRequest = $.ajax({
            url: API_BASEURL + "needsWifiChange",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
 			timemout:10 * 1000,
           	data: JSON.stringify(self.wifiUIState),
            complete: function(response) {
            	self.save(response.responseJSON);
            }
        });
    }

	// TYPEA: make the save flags an instance variable, so we have access to them across multiple callbacks.
	self.saveFlags = {
		'needsWifiConnect': false,
		'needsWifiDisabled': false,
		'needsWifiSwitch': false
	}

	self.save = function(response)
	{
		if (!"networkSettings" in response) {
			self.disableUI();
			return;
		}

		if (!response || !('wifiNeedsChangeResult' in response)) {
			return;
		}

		var needsChangeResult = response.wifiNeedsChangeResult;
		
		console.log("NetSettings.save(): selectedSSID: " + self.wifiUIState.wifiSelectedSSID + ", wifiPasskey: " + self.wifiUIState.wifiPasskey);

		self.saveFlags['needsWifiConnect'] = false;
		self.saveFlags['needsWifiDisabled'] = false;
		self.saveFlags['needsWifiSwitch'] = false;

		if ('wifiNeedsChangeFlags' in needsChangeResult)
		{
			console.log("NetSettings.save(): getting wifiNeedsChangeFlags.");
	
			if ('needsWifiConnect' in needsChangeResult.wifiNeedsChangeFlags)
				self.saveFlags['needsWifiConnect'] = needsChangeResult.wifiNeedsChangeFlags.needsWifiConnect;
			if ('needsWifiDisabled' in needsChangeResult.wifiNeedsChangeFlags)
				self.saveFlags['needsWifiDisabled'] = needsChangeResult.wifiNeedsChangeFlags.needsWifiDisabled;
			if ('needsWifiSwitch' in needsChangeResult.wifiNeedsChangeFlags)
				self.saveFlags['needsWifiSwitch'] = needsChangeResult.wifiNeedsChangeFlags.needsWifiSwitch;
		}
		
		console.log("needsWifiChange = " + self.saveFlags['needsWifiConnect']  + " " + self.saveFlags['needsWifiDisabled'] + " " + self.saveFlags['needsWifiSwitch']);

		if (!self.saveFlags['needsWifiConnect'] && !self.saveFlags['needsWifiDisabled'] && !self.saveFlags['needsWifiSwitch'])
			return;

		var alertHeader = "";
		if (self.saveFlags['needsWifiConnect'] )
			alertHeader = "Connecting printer to wifi network \u201c" + self.wifiUIState.wifiSelectedSSID + "\u201d.";
		else if (self.saveFlags['needsWifiSwitch'])
			alertHeader = "Switching printer to wifi network \u201c" + self.wifiUIState.wifiSelectedSSID + "\u201d.";
		else
			alertHeader = "Turning printer wifi off.";

		$('#wifiAlertHeader').text(alertHeader);

		var self.setWifiResponse = null;
		
		if (!self.wifiAlertEventHandlersInstalled) {
			$('#wifiAlertModal').on('shown', function() { 
				console.log("posting wifi settings change: " + self.wifiUIState.wifiSelectedSSID);
			
				// TYPEA: post the new wifi settings to the server once our modal is show. This will prevent access to
				// the rest of the Octoprint UI until the server responds.
				$.ajax({
					url: API_BASEURL + "setWifiSettings",
					type: "POST",
					timemout:6 * 60 * 1000,
					dataType: "json",
					contentType: "application/json; charset=UTF-8",
					data: JSON.stringify(self.wifiUIState),
					complete: function(response) {
						console.log("setWifiSettings POST complete");
						setWifiResponse = response.responseJSON;
						$('#wifiAlertModal').modal('hide');
					}
				});
			});

			$('#wifiAlertModal').on('hidden', function() { 
				self.displaySaveResult();
			});
			
			self.wifiAlertEventHandlersInstalled = true;
		}

		$('#wifiAlertModal').modal('show');
	}

	self.displaySaveResult = function() {
		var changeResult = self.setWifiResponse.wifiSettingsChangeResult
		console.log("Change result: " + " " + changeResult)
		self.networkConnectFlags = {
		'succeeded' : false,
		'authenticateFailed' : false,
		'ssidNotFound' : false,
		'osFailure' : false
		}
	
		if ('succeeded' in changeResult.wifiSettingsChangeResultFlags)
			self.networkConnectFlags['succeeded'] = changeResult.wifiSettingsChangeResultFlags.succeeded;
		if ('authenticateFailed' in changeResult.wifiSettingsChangeResultFlags)
			self.networkConnectFlags['authenticateFailed'] = changeResult.wifiSettingsChangeResultFlags.authenticateFailed;
		if ('ssidNotFound' in changeResult.wifiSettingsChangeResultFlags)
			self.networkConnectFlags['ssidNotFound'] = changeResult.wifiSettingsChangeResultFlags.ssidNotFound;
		if ('osFailure' in changeResult.wifiSettingsChangeResultFlags)
			self.networkConnectFlags['osFailure'] = changeResult.wifiSettingsChangeResultFlags.osFailure;		
	
		// TYPEA: do something to notify the user about whether the settings change worked.
		if (self.networkConnectFlags['succeeded'])
			$.pnotify({title: "Connection successful", text: "You are now connected to \"" + self.selectedSSID + "\"", type: "success"});
		else if(self.networkConnectFlags['authenticateFailed'])
			$.pnotify({title: "Connection failed", text: "The password you entered is incorrect. Please try again.", type: "error"});
		else if(self.networkConnectFlags['ssidNotFound'])
			$.pnotify({title: "Connection failed", text: "The network \"" + self.selectedSSID + "\"" + " was not found.", type: "error"});
		else
			$.pnotify({title: "Connection failed", text: "A connection failure has occurred. Please try again.", type: "error"});
	}

	self.wifiEnabledUIState = {
		'wifiEnabled': false
	}

	self.wifiEnabledCBoxDidChange = function(enabled) {
		// TYPEA: don't try to toggle wifi on or off before the UI state is fully updated.
		if (!self.uiInitialized)
			return;
			
		self.wifiEnabledUIState['wifiEnabled'] = enabled;

		console.log("wifi enabled checkbox clicked: " + enabled);

		if (enabled)
			self.selectize.enable();
		else
			self.selectize.disable();

		$("#settings-wifipasskey").prop("disabled", !enabled);

		$.ajax({
			url: API_BASEURL + "needsWifiEnabled",
			type: "POST",
			dataType: "json",
			contentType: "application/json; charset=UTF-8",
			timemout:10 * 1000,
			data: JSON.stringify(self.wifiEnabledUIState),
			complete: function(response) {
				console.log('needsWifiEnabled requested posted.');
				self.enableWifi(response.responseJSON);
			}
		});
	}


	self.enableWifi = function(response) {
		if (!self.wifiEnableAlertEventHandlersInstalled)
		{
			$('#wifiEnableModal').on('shown', function() { 
				console.log("posting wifi enable change: " + self.wifiEnabledUIState.wifiEnabled);
			
				// TYPEA: tell the server to enable wifi once the modal is shown. This will prevent access to the rest
				// of the Octoprint UI until the server responds.
				$.ajax({
					url: API_BASEURL + "enableWifi",
					type: "POST",
					timemout:6 * 60 * 1000,
					dataType: "json",
					contentType: "application/json; charset=UTF-8",
					data: JSON.stringify(self.wifiEnabledUIState),
					complete: function(response) {
						console.log("enableWifi POST complete");
						self.setWifiResponse = response.responseJSON;
						
						// TYPEA: hide the modal once we get a response back from the server.
						$('#wifiEnableModal').modal('hide');
					}
				});
			});

			$('#wifiEnableModal').on('hidden', function() {
				// TYPEA: refresh the net settings UI when the modal is hidden. The modal is hidden once the server has
				// finished enabling wifi, so at that point we need to update the UI to show that wifi is enabled and
				// list any visible wifi networks. 
				self.refreshUI();
			});

			self.wifiEnableAlertEventHandlersInstalled = true;
		}

		console.log('enableWifi(): response: ');
		console.log(response);

		if (('wifiNeedsEnabled' in response.wifiNeedsEnabledResult) && response.wifiNeedsEnabledResult['wifiNeedsEnabled']) {
			console.log('showing wifi enabled delay modal');
			$('#wifiEnableModal').modal('show');
		}
	}

	console.log("NetSettings() done.");
}

