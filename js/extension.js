(function() {
    class Bluetoothpairing extends window.Extension {
        constructor() {
            super('bluetoothpairing');
            //console.log("Adding bluetoothpairing addon to menu");
            this.addMenuEntry('Bluetooth pairing');

            this.debug = false;
            
            this.content = '';

            this.item_elements = ['name', 'address'];
            this.all_things;
            this.items_list = [];

            this.item_number = 0;
            

            fetch(`/extensions/${this.id}/views/content.html`)
                .then((res) => res.text())
                .then((text) => {
                    this.content = text;
        			if( document.location.href.endsWith("/extensions/bluetoothpairing") ){
                        //console.log('followers: calling this.show from constructor init because at /followers url');
        				this.show();
        			}
                })
                .catch((e) => console.error('Failed to fetch content:', e));
        }



        show() {
            
            if(this.content == ''){
                //console.log("aborting show - content not loaded yet");
                return;
            }
            
            //console.log('in show');
            
            this.view.innerHTML = this.content;
            //console.log("bluetoothpairing show called");
			
            
            // Click event for ADD button
            document.getElementById("extension-bluetoothpairing-add-button").addEventListener('click', () => {
                //this.items_list.push({'enabled': false});
                document.getElementById('extension-bluetoothpairing-content').classList.add('extension-bluetoothpairing-scanning');
                this.scan_start();
            });


            document.getElementById("extension-bluetoothpairing-title").addEventListener('click', () => {
                this.scan_poll(true);
            });


            this.scan_poll(true);
            
        }

        
        scan_start() {
            //console.log("calling for scan start");
            //document.getElementById('extension-bluetoothpairing-list-discovered').innerHTML = "";
            const list = document.getElementById('extension-bluetoothpairing-list-paired');
            window.API.postJson(
                `/extensions/${this.id}/api/scan`

            ).then((body) => {

                this.scanning = body.scanning;
                this.scan_poll();
                
                this.debug = body.debug;
                if(this.debug){
                    console.log("Python API /scan result:");
                    console.log(body);
                    document.getElementById('extension-bluetoothpairing-warning').style.display = 'block';
                }

            }).catch((e) => {
                console.log("bluetoothpairing: /scan error: ", e);
                list.innerText = "Unable to initiate scan - controller connection error?";
            })
            
            document.getElementById('extension-bluetoothpairing-progress-bar').style.width = '0';
            
        }
        

        scan_poll(get_paired=false) {
			//console.log("in scan_poll. get_paired: ", get_paired);
			const list = document.getElementById('extension-bluetoothpairing-list-paired');

            if(list == null){
                console.log('Error: list output div did not exist yet?');
                return
            }

            window.API.postJson(
                `/extensions/${this.id}/api/poll`,
                {'get_paired':get_paired}

            ).then((body) => {
                if(this.debug){
                    console.log("Python API /poll result:");
                    console.log(body);
                }

                this.scanning = body.scanning;
            
                if(typeof body.scanning != 'undefined'){
                    if(body.scanning){
                        //console.log("poll: controller is scanning");
                        document.getElementById('extension-bluetoothpairing-content').classList.add('extension-bluetoothpairing-scanning');
                    
                        if(typeof body.scan_progress != 'undefined'){
                            document.getElementById('extension-bluetoothpairing-progress-bar').style.width = body.scan_progress + '%';
                        }
                        //console.log('scanning, so creating a timeout');
                        window.setTimeout( () =>{
                            this.scan_poll();
                        },1000);
                    }
                    else{
                        //console.log("poll: controller is NOT scanning");
                        //document.getElementById('extension-bluetoothpairing-list-paired').innerHTML = "";
                        //document.getElementById('extension-bluetoothpairing-list-trackers').innerHTML = "";
                        //document.getElementById('extension-bluetoothpairing-list-discovered').innerHTML = "";
                        this.regenerate_items(body['all_devices']);
                        document.getElementById('extension-bluetoothpairing-content').classList.remove('extension-bluetoothpairing-scanning');
                    }
                }
                

            }).catch((e) => {
                console.log("bluetoothpairing: /poll error: ", e);
                list.innerText = "Unable to poll scan results - controller connection error?";
            })
            
        }
        





        //
        //  REGENERATE ITEMS
        //

        regenerate_items(items) {
            if(this.debug){
                console.log("regenerating list. Items: ");
                console.log(items);
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
                    
                    var list_name = 'discovered';
                    var list = document.getElementById('extension-bluetoothpairing-list-discovered');
                    
					if( items[item]['paired'] == true ){
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
                        
                        const rssi_opacity = 0.5 + (items[item]['rssi'] + 100) / 50;
                        var rssi_percentage = (items[item]['rssi'] + 100) * 1.25;
                        if(rssi_percentage > 100){rssi_percentage = 100;}
                        
                        clone.querySelector('.extension-bluetoothpairing-item-rssi-container').innerHTML = '<div class="extension-bluetoothpairing-item-rssi-image-container" style="opacity:' + rssi_opacity + '"><div class="extension-bluetoothpairing-item-rssi-image-cutoff" style="width:' + rssi_percentage + '%"><img class="extension-bluetoothpairing-item-rssi-image" src="/extensions/bluetoothpairing/images/signal-indicator.svg" alt="RSSI: ' + items[item]['rssi'] + '"/></div></div><span class="extension-bluetoothpairing-item-rssi-value">' + items[item]['rssi']+ '</span>';

                    }
                    
                    
                    

                    // Add manufacturer
                    if(typeof items[item]['manufacturer'] != 'undefined'){   
                        clone.querySelector('.extension-bluetoothpairing-manufacturer').innerText = items[item]['manufacturer'];
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
					if(typeof items[item]['binary'] != 'undefined'){
					    info_panel.innerHTML = items[item]['binary'];
					}
                    

                    
                    // Pair button click event
                    const pair_button = clone.querySelectorAll('.extension-bluetoothpairing-item-pair-button')[0];
                    
                    if(list_name == 'paired'){
                        
                        // UNpairing or an already paired device
                        pair_button.addEventListener('click', (event) => {
                            //console.log("unpair button clicked");
                            //console.log(event);
                            
                            var target = event.currentTarget;
                            var main_item = this.getClosest(event.currentTarget,'.extension-bluetoothpairing-item');
                            //var main_item = target.parentElement.parentElement.parentElement; //parent of "target"
                            
                            //console.log(main_item);
                            main_item.classList.add("extension-bluetoothpairing-item-pairing");
    						

                            // Communicate with backend
                            window.API.postJson(
                                `/extensions/${this.id}/api/update`, {
                                    'mac': mac,
                                    'action': 'unpair'
                                }
                            ).then((body) => {
                                //thing_list.innerText = body['state'];
                                //console.log("unpair response: ", body);
                            
                                if (body['state'] != 'ok') {
                                    if( body['state'] == true ){
                                        //console.log("unpair succeeded");
                                        window.setTimeout(() => {
                                            this.scan_poll(true); // will redraw the lists
                                        },3000);
    									
                                    }
                                    //else{
                                        //info_panel.innerHTML = "Unpairing failed";
                                    //}
                                }
    							main_item.classList.remove("extension-bluetoothpairing-item-pairing");
							
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
                                

                            }).catch((e) => {
                                console.log("bluetoothpairing: server connection error while pairing: ", e);
    							info_panel.innerHTML = "Error connecting to server";
    							main_item.classList.remove("extension-bluetoothpairing-item-pairing");
                                
                            });
                        });
                    }
                    else{
                        
                        // Normal pairing of a discovered device
                        pair_button.addEventListener('click', (event) => {
                            //console.log("pair button clicked");
                            //console.log(event);
                            
                            var target = event.currentTarget;
                            //var main_item = target.parentElement.parentElement.parentElement; //parent of "target"
                            var main_item = this.getClosest(event.currentTarget,'.extension-bluetoothpairing-item');
                            //console.log(main_item);
                            main_item.classList.add("extension-bluetoothpairing-item-pairing");
    						//const info_panel = main_item.querySelectorAll('.extension-bluetoothpairing-item-info')[0];

                            // Communicate with backend
                            window.API.postJson(
                                `/extensions/${this.id}/api/update`, {
                                    'mac': mac,
                                    'action': 'pair'
                                }
                            ).then((body) => {
                                //thing_list.innerText = body['state'];
                                //console.log("pair response: ", body);
                            
                                if (body['state'] != 'ok') {
                                    if( body['state'] == true ){
                                        //console.log("pairing succesfull");
    									main_item.classList.add("extension-bluetoothpairing-item-paired");
                                        main_item.classList.remove("extension-bluetoothpairing-item-pairing-failed");
                                        this.scan_poll(true); // redraws the lists
                                    }
                                    else if( body['state'] == false ){
                                        //console.log("pairing failed");
    									main_item.classList.add("extension-bluetoothpairing-item-pairing-failed");
                                        main_item.classList.remove("extension-bluetoothpairing-item-paired");
                                    }
    								else{
                                        //console.log("pairing: else state: ", body['state']);
    									//pre.innerText = body['state'];
    								}
                                }
    							main_item.classList.remove("extension-bluetoothpairing-item-pairing");
							
    							/*
                                info_panel.innerHTML = "";
							
    							for (var i = 0; i < body['update'].length; i++) {
    								info_panel.innerHTML = info_panel.innerHTML + '<span class="">' + body['update'][i] + '</span>';
    							}
                                */

                            }).catch((e) => {
                                //console.log("bluetoothpairing: server connection error while pairing: " + e.toString());
                                //pre.innerText = e.toString();
    							info_panel.innerHTML = "Error connecting to server";
    							main_item.classList.remove("extension-bluetoothpairing-item-pairing");
                            
                                
                            });
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
                        info_panel.style.display = 'block';
                        //console.log(main_item);
                        //main_item.classList.add("info");
                        /*
                        // Communicate with backend
                        window.API.postJson(
                            `/extensions/${this.id}/api/update`, {
                                'mac': mac,
                                'action': 'info'
                            }
                        ).then((body) => {
                            //thing_list.innerText = body['state'];
                            //console.log("info response: ", body);
                            if (body['state'] != 'ok') {
                                //console.log(body['state']);
                                //pre.innerText = body['state'];
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
							
                            
                        }).catch((e) => {
                            console.log("bluetoothpairing: server connection error while pairing: ", e);
                            //pre.innerText = e.toString();
                            
                        });
                        */
                    });
					
                    // Add checkbox click event
                    const checkbox = clone.querySelectorAll('.switch-checkbox')[0];
                    
                    checkbox.addEventListener('change', (event) => {
                        
                        var target = event.currentTarget;
                        var main_item = this.getClosest(target,'.extension-bluetoothpairing-item');
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
                                //thing_list.innerText = body['state'];
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
                                
                            }).catch((e) => {
                                console.log("bluetoothpairing: server connection error while pairing: ",e);
                                
                            });

                        } else {
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
                                //thing_list.innerText = body['state'];
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
										//pre.innerText = body['state'];
                                        
                                        main_item.classList.add('extension-bluetoothpairing-item-connected');
                                        
                                        //console.log('will attempt to trust the device');
                                        
                                        window.API.postJson(
                                            `/extensions/${this.id}/api/update`, {
                                                'mac': mac,
                                                'action': 'trust'
                                            }
                                        ).then((body) => {
                                            //thing_list.innerText = body['state'];
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
            								

                                        }).catch((e) => {
                                            //console.log("bluetoothpairing: server connection error while connecting: ", e);
                                            //pre.innerText = e.toString();
                                            
                                        });
                                        
									}
                                }
                                //console.log("removing connecting class for element: ", main_item);
								main_item.classList.remove("extension-bluetoothpairing-item-connecting");
								//main_item.querySelectorAll('.extension-bluetoothpairing-item-info')[0].innerHTML = body['update'];


                            }).catch((e) => {
                                console.log("bluetoothpairing: server connection error while connecting: ", e);
                            });
                        }
                    });
					if(typeof items[item]['name'] != 'undefined'){
					    clone.querySelector('.extension-bluetoothpairing-name').innerText = items[item]['name']
					}
                    else{
                        clone.querySelector('.extension-bluetoothpairing-name').innerText = items[item]['address']
                    }
                    
                    clone.querySelector('.extension-bluetoothpairing-address').innerText = items[item]['address']
                    
                    
                    // Update to the actual values of regenerated item
                    /*
                    for (var key in this.item_elements) { // name and mac
                        console.log('key: ', key);
                        try {
                            if (this.item_elements[key] != 'enabled') {
                                clone.querySelectorAll('.extension-bluetoothpairing-' + this.item_elements[key])[0].innerText = items[item][this.item_elements[key]];
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
                    
                }
                
                if(paired_counter == 0){
                    paired_list.innerHTML = "There are no paired devices";
                }

            } catch (e) {
                console.log("bluetoothpairing: error regenerating: ", e);
            }
        }



        getClosest(elem, selector) {
        	for ( ; elem && elem !== document; elem = elem.parentNode ) {
        		if ( elem.matches( selector ) ) return elem;
        	}
        	return null;
        };


		hide(){
			//console.log("hiding bluetooth extension");
			this.view.innerHTML = "";
		}

    }

    new Bluetoothpairing();

})();