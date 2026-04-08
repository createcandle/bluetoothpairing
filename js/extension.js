(function() {
    class Bluetoothpairing extends window.Extension {
        constructor() {
            super('bluetoothpairing');
            //console.log("Adding bluetoothpairing addon to menu");
            this.addMenuEntry('Bluetooth');

            this.debug = false;
            
            this.content = '';
			this.previous_stringified_items = '';

            this.item_elements = ['name', 'address'];
            this.all_things;
            this.items_list = [];

            this.item_number = 0;
			
			this.content_el = null;
			this.debug_warning_revealed = false;
			
			this.page_visible = true;
			document.addEventListener("visibilitychange", () => {
			  if (document.hidden) {
				  if(this.debug){
					  console.log("bluetooth debug: page became hidden");
				  }
				  this.page_visible = false;
			  } else {
				  if(this.debug){
					  console.log("bluetooth debug: page became visible");
				  }
				  this.page_visible = true;
			  }
			});
            

            fetch(`/extensions/${this.id}/views/content.html`)
            .then((res) => res.text())
            .then((text) => {
                this.content = text;
    			if( document.location.pathname == "/extensions/bluetoothpairing" ){
                    //console.log('bluetoothpairing: calling this.show from constructor init because started at url');
    				this.show();
    			}
            })
            .catch((e) => console.error('bluetooth: failed to fetch content:', e));
				
			this.get_paired = false;
			this.busy_polling = false;
			this.main_interval = setInterval(() => {
				this.do_poll();
			},3000);
        }



        show() {
            //console.log('bluetoothpairing: in show');
            if(this.content == ''){
                //console.log("aborting show - content not loaded yet");
                return;
            }
            
			this.debug_warning_revealed = false;
			
            //console.log('in show');
            this.view.innerHTML = this.content;
            //console.log("bluetoothpairing show called");
			
			this.content_el = this.view.querySelector('#extension-bluetoothpairing-content');
            
            // Click event for ADD button
            this.view.querySelector('#extension-bluetoothpairing-add-button').addEventListener('click', () => {
                //this.items_list.push({'enabled': false});
                this.content_el.classList.add('extension-bluetoothpairing-scanning');
                this.scan_start();
            });

			const title_el = this.view.querySelector('#extension-bluetoothpairing-title');
            title_el.addEventListener('click', () => {
				this.get_paired = true;
				if(title_el.classList.contains('extension-bluetoothpairing-title-real-bluetooth')){
					title_el.classList.remove('extension-bluetoothpairing-title-real-bluetooth');
					title_el.classList.add('extension-bluetoothpairing-title-realer-bluetooth');
				}
				else if(title_el.classList.contains('extension-bluetoothpairing-title-realer-bluetooth')){
					title_el.classList.remove('extension-bluetoothpairing-title-realer-bluetooth');
				}
				else{
					title_el.classList.add('extension-bluetoothpairing-title-real-bluetooth');
				}
            });
			
			const un_shh_button_el = this.view.querySelector('#extension-bluetoothpairing-re-enable-button');
			if(un_shh_button_el){
	            un_shh_button_el.addEventListener('click', () => {
					un_shh_button_el.classList.add('extension-bluetoothpairing-faded');
		            window.API.postJson(
		                `/extensions/${this.id}/api/ajax`,
						{'action':'un-shh'}

		            ).then((body) => {
						if(this.debug){
							console.log("bluetooth debug: un-shh response: ", body);
						}
						this.view.querySelector('#extension-bluetoothpairing-do-not-scan-until').classList.add('extension-bluetoothpairing-hidden');
						un_shh_button_el.classList.remove('extension-bluetoothpairing-faded');
		            }).catch((err) => {
		                if(this.debug){
							console.error("bluetooth: caught error calling /ajax with un-shh: ", err);
						}
						un_shh_button_el.classList.remove('extension-bluetoothpairing-faded');
		            })
	            });
			}
			
        }



        // Periodic polling
		do_poll(){
            if(this.debug){
				console.log("bluetooth debug: in do_poll. this.page_visible,this.busy_polling: ", this.page_visible,this.busy_polling);
			}
			if(this.page_visible && window.location.pathname == '/extensions/bluetoothpairing' && this.busy_polling == false){
				this.busy_polling = true;
			    window.API.postJson(
	                `/extensions/${this.id}/api/poll`,
	                {'get_paired':this.get_paired}

	            ).then((body) => {
	                if(this.debug){
	                    console.log("bluetooth denug: got API /poll response. this.get_paired,body: ", this.get_paired, body);
	                }
					this.parse_body(body);
					this.busy_polling = false;
	            }).catch((err) => {
	                if(this.debug){
						console.error("bluetooth debug: caught error calling /poll with get_paired: ", this.get_paired, err);
					}
					this.busy_polling = false;
	                //list.textContent = "Unable to get scan results - controller connection error?";
	            })
				
				if(this.get_paired == true){
					this.get_paired = false;
					if(this.debug){
						console.log("bluetooth: did a poll request that also asked for an update of the currently paired devices list");
					}
					
				}
			}
			
		}
		
		
		
		
		
		
		
        scan_start() {
            //console.log("calling for scan start");
            //document.getElementById('extension-bluetoothpairing-list-discovered').innerHTML = "";
            const list = this.view.querySelector('#extension-bluetoothpairing-list-paired');
            window.API.postJson(
                `/extensions/${this.id}/api/scan`

            ).then((body) => {
				this.parse_body(body);

            }).catch((err) => {
                if(this.debug){
					console.error("bluetooth: caught error calling /scan: ", err);
				}
                list.textContent = "Unable to initiate scan - controller connection error?";
            })
            
            document.getElementById('extension-bluetoothpairing-progress-bar').style.width = '0';
            
        }
        

		parse_body(body){

            if(typeof body.debug == 'boolean'){
            	this.debug = body.debug;
            }
            
            if(this.debug){
                if(this.debug){
					console.log("bluetooth: in parse_body.  body: ", body);
				}
				if(this.debug_warning_revealed == false){
					this.debug_warning_revealed = true;
					const debug_warning_el = this.view.querySelector('#extension-bluetoothpairing-warning');
					if(debug_warning_el){
						debug_warning_el.style.display = 'block';
					}
				}
            }
			
			
            if(typeof body.scanning == 'boolean'){
				this.scanning = body.scanning;
				
				//const list = document.getElementById('extension-bluetoothpairing-list-paired');
				
				this.content_el = this.view.querySelector('#extension-bluetoothpairing-content');
				
				
                if(body.scanning){
                    if(this.debug){
						console.log("\n\n ( ( ( - ) ) ) \n\nbluetooth debug: poll: controller is scanning");
					}
                    if(this.content_el){
                        this.content_el.classList.add('extension-bluetoothpairing-scanning');
                    
					
	                    if(typeof body.scan_progress != 'undefined'){
							const scanning_progress_bar_el = this.view.querySelector('#extension-bluetoothpairing-progress-bar');
	                        if(scanning_progress_bar_el){
								scanning_progress_bar_el.style.width = body.scan_progress + '%';
							}
	                    }
						
					}
                
                   
                    //console.log('scanning, so creating a timeout');
                    /*
					window.setTimeout( () =>{
                        this.scan_poll();
                    },1000);
					*/
                }
                else{
                    //console.log("poll: controller is NOT scanning");
                    //document.getElementById('extension-bluetoothpairing-list-paired').innerHTML = "";
                    //document.getElementById('extension-bluetoothpairing-list-trackers').innerHTML = "";
                    //document.getElementById('extension-bluetoothpairing-list-discovered').innerHTML = "";
                   
                    if(this.content_el){
	                    if(typeof body['all_devices'] != 'undefined'){
	                    	this.regenerate_items(body['all_devices']);
	                    }
                        this.content_el.classList.remove('extension-bluetoothpairing-scanning');
                    }
                    
                }
            }
			
			if(typeof body.do_not_scan_until_remaining == 'number'){
				this.do_not_scan_until_remaining = body.do_not_scan_until_remaining;
				const do_not_scan_until_el = this.view.querySelector('#extension-bluetoothpairing-do-not-scan-until');
                if(do_not_scan_until_el){
					if(this.do_not_scan_until_remaining > 0){
						this.view.querySelector('#extension-bluetoothpairing-do-not-scan-until-remaining').textContent = 'In ' + this.do_not_scan_until_remaining + ' seconds scanning will be re-enabled automatically.';
						do_not_scan_until_el.classList.remove('extension-bluetoothpairing-hidden');
					}
					else{
						do_not_scan_until_el.classList.add('extension-bluetoothpairing-hidden');
					}
				}
			}
			
		}
		



		

        //
        //  REGENERATE ITEMS
        //

        regenerate_items(items) {
			if(typeof items == 'undefined' || items == null){
				if(this.debug){
					console.error("bluetooth debug: regenerate_items: aborting, invalid items provided: ", items);
				}
				return
			}
			
			let items_clone = JSON.parse(JSON.stringify(items));
			items_clone.forEach(obj => delete obj.last_seen);
			const stringified_items = JSON.stringify(items_clone);
			if(stringified_items == this.previous_stringified_items){
				if(this.debug){
					console.log("bluetooth debug: regenerate_items: no real change in devices, aborting redrawing list");
				}
				return
			}
			
			this.previous_stringified_items = stringified_items;
            if(this.debug){
                console.log("bluetooth debug: in regenerate_items.  items: ", items);
            }
            const original = document.getElementById('extension-bluetoothpairing-original-item');
            const paired_list = document.getElementById('extension-bluetoothpairing-list-paired');
            const discovered_list = document.getElementById('extension-bluetoothpairing-list-discovered');
            const tracker_list = document.getElementById('extension-bluetoothpairing-list-trackers');

            if(paired_list == null){
                //console.log('no HTML to generate into (yet)');
                return;
            }
            paired_list.innerHTML = "";
            discovered_list.innerHTML = "";
            tracker_list.innerHTML = "";
            //console.log('items.length: ', items.length);
            
            var paired_counter = 0;
            this.item_number = 0; // used to generated unique toggle IDs

            try {
                
                items.sort((a, b) => (a.name.toLowerCase() > b.name.toLowerCase()) ? 1 : -1) // sort alphabetically

                // Loop over all items
                for (var item in items) {
                    
                    //console.log(items[item]);
                    
                    var list_name = 'discovered';
                    var list = document.getElementById('extension-bluetoothpairing-list-discovered');
                    
					if( items[item]['paired'] == true ){
                        //console.log('paired item');
                        list_name = 'paired';
                        paired_counter++;
                        list = document.getElementById('extension-bluetoothpairing-list-paired');
					}
                    else if( items[item]['type'] == 'tracker' ){
                        list_name = 'trackers';
                        list = document.getElementById('extension-bluetoothpairing-list-trackers');
					}
                    
					//console.log(items[item]);
                    var clone = original.cloneNode(true);
                    clone.removeAttribute('id');

                    //console.log(items[item]['mac']);
                    
                    const nice_name = items[item]['name'];
					const mac = items[item]['address'];
                    const safe_mac = mac.replace(/:/g, "-");
                    clone.removeAttribute('id');
                    clone.setAttribute('id', safe_mac);


                    // Add icon
                    if(items[item]['name'] == 'Airtag'){
                        //console.log('adding icon');
                        clone.querySelector('.extension-bluetoothpairing-item-icon-container').innerHTML = '<img src="/extensions/bluetoothpairing/images/airtag-icon.svg" alt="Airtag icon"/>';
                    }
                    
                    if(typeof items[item]['rssi'] != 'undefined'){
                        //console.log('rssi: ', items[item]['rssi']);
                        
                        const rssi = parseInt(items[item]['rssi']);
                        const rssi_opacity = 0.5 + (rssi + 100) / 50;
                        var rssi_percentage = (rssi + 100) * 1.25;
                        if(rssi_percentage > 100){rssi_percentage = 100;}
                        
                        clone.querySelector('.extension-bluetoothpairing-item-rssi-container').innerHTML = '<div class="extension-bluetoothpairing-item-rssi-image-container" style="opacity:' + rssi_opacity + '"><div class="extension-bluetoothpairing-item-rssi-image-cutoff" style="width:' + rssi_percentage + '%"><img class="extension-bluetoothpairing-item-rssi-image" src="/extensions/bluetoothpairing/images/signal-indicator.svg" alt="RSSI: ' + items[item]['rssi'] + '"/></div></div><span class="extension-bluetoothpairing-item-rssi-value">' + items[item]['rssi'] + '</span>';

                    }
                    

                    // Add manufacturer
                    if(typeof items[item]['manufacturer'] == 'string'){   
                        clone.querySelector('.extension-bluetoothpairing-manufacturer').textContent = items[item]['manufacturer'];
                    }


					// Add class to reflect paired state
					if( items[item]['paired'] == true ){
						//console.log("ENABLED");
						clone.classList.add("extension-bluetoothpairing-item-paired");
					}
					

                    // Change switch icon to reflect connected state
                    clone.querySelectorAll('.switch-checkbox')[0].id =    list_name + 'toggle-' + this.item_number;
                    clone.querySelectorAll('.switch-slider')[0].htmlFor = list_name + 'toggle-' + this.item_number;
                    this.item_number++;


					const info_panel = clone.querySelector('.extension-bluetoothpairing-item-info');
					if(info_panel && typeof items[item]['binary'] != 'undefined'){
					    info_panel.innerHTML = items[item]['binary'];
					}
                    

                    
                    // Pair button click event
                    const pair_button = clone.querySelectorAll('.extension-bluetoothpairing-item-pair-button')[0];
                    
                    if(list_name == 'paired'){
                        
                        // UNpairing or an already paired device
                        pair_button.addEventListener('click', (event) => {
                            //console.log("unpair button clicked");
                            //console.log(event);
                            info_panel.innerHTML = '';
                            //const target = event.currentTarget;
                            const main_item = event.currentTarget?.closest('.extension-bluetoothpairing-item');
                            //var main_item = target.parentElement.parentElement.parentElement; //parent of "target"
                            
							if(main_item){
								main_item.classList.add("extension-bluetoothpairing-item-pairing");
	                            //console.log(main_item);
                            
    						
                            

	                            // Communicate with backend
	                            window.API.postJson(
	                                `/extensions/${this.id}/api/update`, {
	                                    'mac': mac,
	                                    'action': 'unpair'
	                                }
	                            ).then((body) => {
	                                //thing_list.textContent = body['state'];
	                                if(this.debug){
	                                    console.log("bluetooth debug: unpair response: ", body);
	                                }
                            
	                                if (typeof body.state == 'boolean') {
	                                    if( body.state == true ){
			                                if(this.debug){
			                                    console.log("bluetooth debug: successful unpairing -> asking for next poll to return all devices list, : ", body);
			                                }
											this.get_paired = true; // next poll will request updated paired devices list, which will then redraw the list
	                                    }
	                                }
	    							main_item?.classList.remove("extension-bluetoothpairing-item-pairing");
							
	    							/*
	    							if( Array.isArray(body['update'])){
	        							for (var i = 0; i < body['update'].length; i++) {
	        								info_panel.innerHTML = info_panel.innerHTML + '<span>' + body['update'][i] + '</span>';
	        							}
	    							}
	                                else{
	                                    info_panel.innerHTML = info_panel.innerHTML + '<span>' + body['update'] + '</span>';
	                                }
	                                */
                                

	                            }).catch((err) => {
	                                if(this.debug){
										console.log("bluetooth debug: caught error calling /update to unpair a device: ", err);
									}
	    							info_panel.innerHTML = "Error connecting to controller";
	    							main_item?.classList.remove("extension-bluetoothpairing-item-pairing");
                                
	                            });
							}
							
                        });
                    }
                    else{
                        
                        // Normal pairing of a discovered device
                        pair_button.addEventListener('click', (event) => {
                            //console.log("pair button clicked");
                            //console.log(event);
                            
                            info_panel.innerHTML = '';
                            //var main_item = target.parentElement.parentElement.parentElement; //parent of "target"
                            const main_item = event.currentTarget?.closest(event.currentTarget,'.extension-bluetoothpairing-item');
                            //console.log(main_item);
                            if(main_item){
                            	main_item.classList.add("extension-bluetoothpairing-item-pairing");
								
	    						//const info_panel = main_item.querySelectorAll('.extension-bluetoothpairing-item-info')[0];

	                            // Communicate with backend
	                            window.API.postJson(
	                                `/extensions/${this.id}/api/update`, {
	                                    'mac': mac,
	                                    'action': 'pair'
	                                }
	                            ).then((body) => {
	                                //thing_list.textContent = body['state'];
	                                if(this.debug){
	                                    console.log("bluetooth debug: pair response: ", body);
	                                }
                                
	                            	if(typeof body['state'] == 'boolean'){
	                                    if( body['state'] == true ){
	                                        //console.log("pairing succesfull");
	    									main_item.classList.add("extension-bluetoothpairing-item-paired");
	                                        main_item.classList.remove("extension-bluetoothpairing-item-pairing-failed");
	                                        this.get_paired = true;
											//this.scan_poll(true); // redraws the lists
	                                    }
	                                    else{
	                                        //console.log("pairing failed");
	    									main_item.classList.add("extension-bluetoothpairing-item-pairing-failed");
	                                        main_item.classList.remove("extension-bluetoothpairing-item-paired");
	                                    }
    								
	                            	}
	                                if (body['state'] != 'ok') {
                                    
	                                }
	    							main_item.classList.remove("extension-bluetoothpairing-item-pairing");
							
	    							/*
	                                info_panel.innerHTML = "";
							
	    							for (var i = 0; i < body['update'].length; i++) {
	    								info_panel.innerHTML = info_panel.innerHTML + '<span class="">' + body['update'][i] + '</span>';
	    							}
	                                */

	                            }).catch((err) => {
	                                if(this.debug){
										console.error("bluetooth debug: caught server connection error while pairing: ", err);
									}
	                                //pre.textContent = e.toString();
	    							info_panel.innerHTML = "Error connecting to server";
	    							main_item.classList.remove("extension-bluetoothpairing-item-pairing");
	                            });
                            }
    						
                        });
                    }


                    // Info button click event
                    const info_button = clone.querySelectorAll('.extension-bluetoothpairing-address')[0];
                    info_button.addEventListener('click', (event) => {
                        
                        //console.log("secret info button clicked");
                        //console.log(event);
                        var target = event.currentTarget;
                        var main_item = target.parentElement.parentElement.parentElement; //parent of "target"
                        const info_panel = main_item.querySelector('.extension-bluetoothpairing-item-info');
                        info_panel.innerHTML = '';
                        info_panel.style.display = 'block';
                        
                        //console.log(main_item);
                        //main_item.classList.add("info");
                        
                        // Communicate with backend
                        window.API.postJson(
                            `/extensions/${this.id}/api/update`, {
                                'mac': mac,
                                'action': 'info'
                            }
                        ).then((body) => {
                            //thing_list.textContent = body['state'];
                            //console.log("info response: ", body);
                            if (body['state'] != 'ok') {
                                //console.log(body['state']);
                                //pre.textContent = body['state'];
                            }
							
                            if(body['update'] == null || body['update'] == ''){
                                body['update'] = "Device did not respond";
                            }
                            
                            
							const info_panel = main_item.querySelector('.extension-bluetoothpairing-item-info');
							info_panel.innerHTML = "";
							if( Array.isArray(body['update'])){
    							for (var i = 0; i < body['update'].length; i++) {
    								info_panel.innerHTML = info_panel.innerHTML + '<span>' + body['update'][i] + '</span>';
    							}
							}
                            else{
                                info_panel.innerHTML = info_panel.innerHTML + '<span>' + body['update'] + '</span>';
                            }
							
                            
                        }).catch((err) => {
							if(this.debug){
                            	console.error("bluetooth debug: caught error calling /update: ", err);
							}
                            //pre.textContent = e.toString();
                        });
                        
                    });
					
                    // Add checkbox click event
                    const checkbox = clone.querySelector('.switch-checkbox');
                    
                    checkbox.addEventListener('change', (event) => {
                        
                        var target = event.currentTarget;
                        var main_item = this.getClosest(target,'.extension-bluetoothpairing-item');
                        info_panel.innerHTML = '';
                        //var main_item = target.parentElement.parentElement.parentElement.parentElement; //parent of "target"
                        //console.log(main_item);
                        //console.log("this?: ", this);
                        //console.log('event: ', event);


                        const checkbox_element = event.target;
                        //console.log('checkbox element: ', checkbox_element);
                        //console.log('checkbox_element.checked: ', checkbox_element.checked);
                        
                        if (event.currentTarget.checked == false) {
                        //if (checkbox_element.checked == false) {
                            //console.log("checkbox was UNchecked. Event:");
							//console.log(event);

                            // Communicate with backend
                            window.API.postJson(
                                `/extensions/${this.id}/api/update`, {
                                    'mac': mac,
                                    'action': 'disconnect'
                                }
                            ).then((body) => {
                                //thing_list.textContent = body['state'];
                                //console.log("disconnect response: ", body); 
								
								const safe_mac = body['mac'].replace(/:/g, "-");
								main_item = document.getElementById(safe_mac);
								
                                if (body['state'] != 'ok') {
	                                if( body['state'] == false ){
										main_item.querySelectorAll('.extension-bluetoothpairing-enabled')[0].checked = body['state'];
	                                }
									else{
										//console.log("disconnect state ok: ", body['state']);
									}
                                }
								main_item.querySelectorAll('.extension-bluetoothpairing-item-info')[0].innerHTML = body['update'];
                                main_item.classList.remove('extension-bluetoothpairing-item-connected');
                                
                            }).catch((err) => {
								if(this.debug){
									console.error("bluetooth debug: caught server connection error while pairing: ", err);
								}
                                
                            });

                        } 
                        else {
                            //console.log("checkbox was checked. Event:");
							//console.log(event);
							
							main_item.classList.add("extension-bluetoothpairing-item-connecting");

                            // Connect
                            window.API.postJson(
                                `/extensions/${this.id}/api/update`, {
                                    'mac': mac,
                                    'action': 'connect'
                                }
                            ).then((body) => {
                                //thing_list.textContent = body['state'];
                                //console.log("connect response: ", body); 
								
								const safe_mac = body['mac'].replace(/:/g, "-");
								//console.log("safe_mac to find element ID = " + safe_mac);
								//main_item = document.getElementById(safe_mac);
								//console.log("main_item:");
								//console.log(main_item);
                                if (body['state'] != 'ok') { // meaning that it's either true or false, which indicates if the connected succeeded
	                                if( body['state'] == false ){
                                        //console.log('connection failed');
                                        //main_item.classList.remove("extension-bluetoothpairing-item-connecting");
										main_item.querySelectorAll('.extension-bluetoothpairing-enabled')[0].checked = body['state'];
                                        
	                                }
									else{
                                        //console.log("connect: state ok: ", body['state']);
										//pre.textContent = body['state'];
                                        
                                        main_item.classList.add('extension-bluetoothpairing-item-connected');
                                        
                                        //console.log('will attempt to trust the device');
                                        
                                        window.API.postJson(
                                            `/extensions/${this.id}/api/update`, {
                                                'mac': mac,
                                                'action': 'trust'
                                            }
                                        ).then((body) => {
                                            //thing_list.textContent = body['state'];
                                            //console.log("trust response: ", body); 
								
            								const safe_mac = body['mac'].replace(/:/g, "-");
            								//console.log("safe_mac to find element ID = " + safe_mac);
            								//main_item = document.getElementById(safe_mac);
            								//console.log("main_item:");
            								//console.log(main_item);
                                            if (body['state'] != 'ok') { // meaning that it's either true or false, which indicates if the trust succeeded
            	                                if( body['state'] == false ){
                                                    //console.log('trust failed');
            	                                }
            									else{
                                                    //console.log("trust: state ok: ", body['state']);
            									}
                                            }
            								

                                        }).catch((err) => {
											if(this.debug){
												console.error("bluetooth debug: caught error calling /update to trust a device: ", err);
											}
                                        });
                                        
									}
                                }
                                //console.log("removing connecting class for element: ", main_item);
								main_item.classList.remove("extension-bluetoothpairing-item-connecting");
								//main_item.querySelectorAll('.extension-bluetoothpairing-item-info')[0].innerHTML = body['update'];


                            }).catch((err) => {
								if(this.debug){
									console.error("bluetooth debug: caught server connection error while connecting: ", err);
								}
                            });
                        }
                    });
                    
                    // Add name
					if(typeof items[item]['name'] != 'undefined'){
					    clone.querySelector('.extension-bluetoothpairing-name').textContent = items[item]['name']
					}
                    else{
                        clone.querySelector('.extension-bluetoothpairing-name').textContent = items[item]['address']
                    }
                    
                    // Add mac address
                    clone.querySelector('.extension-bluetoothpairing-address').textContent = items[item]['address']
                    
                    
                    // Update to the actual values of regenerated item
                    /*
                    for (var key in this.item_elements) { // name and mac
                        console.log('key: ', key);
                        try {
                            if (this.item_elements[key] != 'enabled') {
                                clone.querySelectorAll('.extension-bluetoothpairing-' + this.item_elements[key])[0].textContent = items[item][this.item_elements[key]];
                            }
                        } catch (e) {
                            console.log("bluetoothpairing: could not regenerate actual values: ", e);
                        }
                    }
                    */

                    // Set connected state of regenerated item
                    
                    clone.querySelectorAll('.extension-bluetoothpairing-enabled')[0].checked = items[item]['connected'];
                    
					if (items[item]['connected'] == true) {
                        //console.log("items seems to be connected.");
                        //clone.querySelectorAll('.extension-bluetoothpairing-enabled')[0].removeAttribute('checked');
                        
                        clone.classList.add('extension-bluetoothpairing-item-connected');
                    }
                    
                    
					if (typeof items[item]['suspiciousness'] != 'undefined') {
                        //console.log("item suspiciousness: ", items[item]['suspiciousness']);
                        //clone.querySelectorAll('.extension-bluetoothpairing-enabled')[0].removeAttribute('checked');
                        
                        clone.classList.add('extension-bluetoothpairing-item-suspiciousness-' + items[item]['suspiciousness']);
                    }
                    else{
                        //console.log("missing suspiciousness value");
                    }
                    
                    if (typeof items[item]['first_seen'] != 'undefined') {
                        const first_seen_spans = clone.querySelectorAll('.extension-bluetoothpairing-item-first-seen');
                        
                        var current_timestamp = new Date().getTime() 
                        current_timestamp = Math.round(current_timestamp / 1000);
                        const first_seen_delta = current_timestamp - items[item]['first_seen'];
                        
                        var first_seen_string = "...";
                        if(first_seen_delta > 3600){
                            var first_seen_date = new Date(items[item]['first_seen'] * 1000);
                            first_seen_string = "on " + first_seen_date.toLocaleDateString() +  " at " + first_seen_date.toLocaleTimeString();
                        }
                        else{
                            first_seen_string = Math.round(first_seen_delta / 60) + " minutes ago";
                        }
                        
                        
                        if(first_seen_string != '...'){
                        	for (var r = 0; r < first_seen_spans.length; r++) {
                                first_seen_spans[r].textContent = first_seen_string;
                        	}
                        }
                        else{
                        	for (var r = 0; r < first_seen_spans.length; r++) {
                                first_seen_spans[r].style.display = 'none';
                        	}
                        }
                        
                    }
                    else{
                        //console.log("Device has no first_seen value");
                    }
                    
                    
                    
					
                    //console.log(items[item]['address'].replace(':','-').replace(':','-').replace(':','-').replace(':','-').replace(':','-'));
					if(document.getElementById(safe_mac) == null){
                        if( items[item]['name'] == items[item]['address'].replace(':','-').replace(':','-').replace(':','-').replace(':','-').replace(':','-') ){
                            clone.classList.add('extension-bluetoothpairing-item-name-is-mac');
                        	list.append(clone);
                        }
    					else{
    						list.prepend(clone);
    					}
					}
                    else{
						if(this.debug){
							console.log("bluetooth debug: odd, that mac was already on the page: ", safe_mac);
						}
                        
                    }
                    
                }
                
                if(paired_counter == 0){
                    paired_list.innerHTML = "There are no paired devices";
                }

            } catch (err) {
				if(this.debug){
					console.error("bluetooth: caught error regenerating: ", err);
				}
            }
        }



		hide(){
			//console.log("hiding bluetooth extension");
			//this.view.innerHTML = "x";
		}

    }

    new Bluetoothpairing();

})();