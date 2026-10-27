# Hot Box
Grant project for measuring thermal performance in different building envelopes.


## Updates

#### Box Hardware (second generation)
Added `box-hardware/` — a single Pico 2 W running both sides of a wall's sensor set
at once (one 3x3 grid + ambient inside, one outside — 20 sensors total), instead of
one standalone Pico per side like the `hardware/` proof of concept. See
`box-hardware/README.md` for wiring and setup.

#### Updated Aug 15, 2025
Setting up the git repo and getting some starter code in place.

Right now we are just capturing and printing out the values in real-time. Next will be to be able to get the file of device information out. This can be manual to start.


#### Next Steps
Eventually we should be able to easily get this information off the device or better yet do it over wifi. Later we'll sync it to a server for real-time information/analysis.

We also need to figure out additional sensors and work on building the box that will do all the monitoring as well.