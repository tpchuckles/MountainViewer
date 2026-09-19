from genTopo import *
import tkinter as tk
import matplotlib,os,ast,glob
from tkinter import *
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
matplotlib.use("Agg") # see also: TDTR_fitting, gui_iSED, and diffractionPredictorUtility
import matplotlib.pyplot as plt

# BUTTON COMBOS:
# shift+click on topo - "stand here, check out the view"
# click on ground-view - "show me where that peak is on the topo"



# TODO: VARIABLE NAMES ARE PSYCHO AND CONFUSING AND PRONE TO BUGS. WE SHOULD REALLY NAIL DOWN THINGS LIKE PSI AND THETA INSTEAD OF X AND Y WHEN REFERRING TO ANGLES, I AND J WHEN REFERRING TO INDICES FOR LAT/LONG, LAT/LON INSTEAD OF X/Y TO AVOID AMBIGUITY, AND SO ON. 

#  ________________
# |   |            |
# | B |  t         |
# | U |   o        |
# | T |    p   p   |
# | T |     o a    |
# | O |      m     |
# | N |____________|
# | S | groundview |
# |___|____________|

# left panel includes:
# first corner lat [entry] lon [entry]
# other corner lat [entry] lon [entry]
# [generate button]
# user will be able to click the topo map of view-from-the-ground to select a standing location, or drop a marker visible on both
#figsize=(6,6)
figwidth=10

window = tk.Tk()

frameLeft=Frame(master=window) ; frameLeft.grid(row=0,column=0,sticky="NSEW")
frameRight=Frame(master=window) ; frameRight.grid(row=0,column=1,sticky="NSEW")
# 1:5 ratio of width for buttons vs plot panel
window.columnconfigure(0,weight=1,uniform="window") ; window.columnconfigure(1,weight=3,uniform="window")
window.rowconfigure(0,weight=1,uniform="window") # one row, set weight to allow it to expand with the window
# top vs bottom panels on the right
frameUpper=Frame(master=frameRight) ; frameUpper.grid(row=0,column=0,sticky="NSEW")
frameLower=Frame(master=frameRight) ; frameLower.grid(row=1,column=0,sticky="NSEW")
# 4:1 ratio of height for area vs ground-view
frameRight.rowconfigure(0,weight=2,uniform="frameR") ; frameRight.rowconfigure(1,weight=1,uniform="frameR")
frameRight.columnconfigure(0, weight=1,uniform="frameR") # one column, set weight to allow it to expand with the window

# defaults. "bounds" will be read from GUI fields or text files, in format of: lat/lon of first corner, lat/lon of opposite corner
resolution=[100,100]			# target resolution (we'll "smart" adjust this for you if the aspect ratio is off)
mark=[[0,0,''],[0,0,'']]		# x,y,c
datahandler=None

named_spots = list(sorted(glob.glob("named_spots/*.txt")))

def load_spot(f):
	print("loading",f)
	global bounds,resolution,mark
	lines = open(f).readlines()
	for l in lines:
		exec(l, globals())
	bounds = np.asarray(bounds)

load_spot(named_spots[-1]) # going to default to the last one for now, solely because this is "Haw Ridge", which is smol, compared to "Afton Mountain Scenic Overlook", which is giganormous.

os.makedirs("figs",exist_ok=True)

# set up buttons/entry panel
def setUpButtons():
	global field_c1lat,field_c1lon,field_c2lat,field_c2lon
	entryWidth=7
	label_c1 = tk.Label(frameLeft,text="first corner:")
	label_c1.grid(row=0,column=0,sticky="NSEW")
	label_c1lat = tk.Label(frameLeft,text="lat:")
	label_c1lat.grid(row=0,column=1,sticky="NSEW")
	field_c1lat=tk.Entry(frameLeft,width=entryWidth)
	field_c1lat.insert(0,str(bounds[0][0]))
	field_c1lat.grid(row=0,column=2,sticky="NSEW")
	label_c1lon = tk.Label(frameLeft,text="lon:")
	label_c1lon.grid(row=0,column=3,sticky="NSEW")
	field_c1lon=tk.Entry(frameLeft,width=entryWidth)
	field_c1lon.insert(0,str(bounds[0][1]))
	field_c1lon.grid(row=0,column=4,sticky="NSEW")
	label_c2 = tk.Label(frameLeft,text="other corner:")
	label_c2.grid(row=1,column=0,sticky="NSEW")
	label_c2lat = tk.Label(frameLeft,text="lat:")
	label_c2lat.grid(row=1,column=1,sticky="NSEW")
	field_c2lat=tk.Entry(frameLeft,width=entryWidth)
	field_c2lat.insert(0,str(bounds[1][0]))
	field_c2lat.grid(row=1,column=2,sticky="NSEW")
	label_c2lon = tk.Label(frameLeft,text="lon:")
	label_c2lon.grid(row=1,column=3,sticky="NSEW")
	field_c2lon=tk.Entry(frameLeft,width=entryWidth)
	field_c2lon.insert(0,str(bounds[1][1]))
	field_c2lon.grid(row=1,column=4,sticky="NSEW")
	button_gen=tk.Button(frameLeft,text="generate")
	button_gen.bind("<Button-1>",generateBoth)
	button_gen.grid(row=2,column=0)
	#label_showRoads=tl.Label(frameLeft,text="show roads?")
	#label_showRoads.grid(row=2,column=1,sticky="NSEW")
	# TODO need tkvar for show roads, then showing should be conditional on that. checkButton can also accept a command= arg to regen
	#check_showRoads=tk.Checkbutton(frameLeft,text="show roads?",onvalue=1,offvalue=0)
	#check_showRoads.grid(row=2,column=1,sticky="NSEW")
	# TODO add dropdown for selecting named_spots. make sure selecting a new named spot updates the lat/lon corners fields

mapObjs={} ; viewObjs={}
def generateBoth(event,regen=True):

	global bounds
	lat1=float(field_c1lat.get()) ; lon1=float(field_c1lon.get())
	lat2=float(field_c2lat.get()) ; lon2=float(field_c2lon.get())

	if abs(min(lat1,lat2)-min(bounds[:,0]))>.01 or\
		abs(max(lat1,lat2)-max(bounds[:,0]))>.01:
		bounds[0,0]=min(lat1,lat2)
		bounds[1,0]=max(lat1,lat2)
	if abs(min(lon1,lon2)-min(bounds[:,1]))>.01 or\
		abs(max(lon1,lon2)-max(bounds[:,1]))>.01:
		bounds[0,1]=min(lon1,lon2)
		bounds[1,1]=max(lon1,lon2)

	if not os.path.exists("gui_elevations.npy"):
		regen=True

	updateTopoMap(regen=regen)
	updateGroundView(lat=None,lon=None,regen=regen)

def updateTopoMap(regen=True):
	global elevations,lats,lons,roads
	# PREP
	global bounds,datahandler
	bounds=np.asarray(bounds)
	if datahandler is None:
		datahandler=srtm.get_data()
		setGlo("datahandler",datahandler)
	fixBoundsAndResolution(bounds,resolution)

	# CALCULATE ELEVATION MAP
	if regen:
		print("calculating elevation map")
		elevations,lats,lons=grid(bounds,resolution,skipInterp=True)
		np.save("gui_elevations.npy",elevations)
		np.save("gui_lats.npy",lats) ; np.save("gui_lons.npy",lons)
	else:
		print("reloading elevation map")
		elevations=np.load("gui_elevations.npy")
		lats=np.load("gui_lats.npy") ; lons=np.load("gui_lons.npy")

	# PLOT IT
	print("updating elevation figure")
	figsize=(figwidth,figwidth)
	mapObjs["fig"],mapObjs["ax"]=plt.subplots(figsize=figsize)	# new empty matplotlib figure/axes objects
	plt.imshow(elevations,cmap="inferno",aspect=1,extent=(min(lons),max(lons),min(lats),max(lats)))
	plt.imsave("figs/topo.png",elevations,cmap="inferno")#,aspect=1,extent=(min(lons),max(lons),min(lats),max(lats)))
	for m in mark:
		if len(m[2])==0:
			continue
		plt.scatter([m[0]],[m[1]],c=m[2],s=20)
	#if check_showRoads
	roads = getRoads(bounds)
	for road in getRoads(bounds):
		lat,lon,name=road
		plt.plot(lon,lat,linewidth=1,c='k')
		if len(name)>0 and len(lon)>1:
			plt.annotate(name,(lon[len(lon)//2],lat[len(lat)//2]))
	if "canvas" in mapObjs.keys():			# if this isn't the first time, destroy the old "canvas" object
		mapObjs["canvas"].get_tk_widget().destroy()
		mapObjs["toolbar"].destroy()
	mapObjs["canvas"] = FigureCanvasTkAgg(mapObjs["fig"], master=frameUpper) # new canvas object to hold the figure
	mapObjs["toolbar"] = NavigationToolbar2Tk(mapObjs["canvas"],frameUpper)	# toolbar, references the canvas
	mapObjs["toolbar"].update()
	mapObjs["canvas"].get_tk_widget().pack(fill='both',expand=True)
	# HANDLE CLICKS
	mapObjs["canvas"].mpl_connect('button_press_event',viewLocationTrigger)	# link callback function to clicks
	#mapObjs["canvas"].mpl_connect('button_press_event',selectRoadTrigger) # FEATURE NOT YET FINISHED

def updateGroundView(lat=None,lon=None,regen=True):
	global distances,phis,thetas,dcoords
	if lon==None:
		lon=np.mean(lons) ; lat=np.mean(lats)

	# GENERATE GROUND VIEW
	if regen or not os.path.exists("gui_distances.npy"):
		print("updating ground view")
		distances,phis,thetas,dcoords=rayTracing(elevations,lats,lons,(lat,lon),"auto",500) # phi is azimuthal angle, theta is vertical
		np.save("gui_distances.npy",distances) ; np.save("gui_dcoords.npy",dcoords)
		np.save("gui_phis.npy",phis) ; np.save("gui_thetas.npy",thetas)
	else:
		print("reloading ground view")
		distances=np.load("gui_distances.npy") ; dcoords=np.load("gui_dcoords.npy")
		phis=np.load("gui_phis.npy") ; thetas=np.load("gui_thetas.npy")

	# PLOT IT
	print("updating ground view figure")
	figsize=(figwidth,figwidth/4)
	viewObjs["fig"],viewObjs["ax"]=plt.subplots(figsize=figsize)	# new empty matplotlib figure/axes objects
	plt.imshow(distances,cmap="inferno",aspect=1,extent=(min(phis),max(phis),min(thetas),max(thetas)))
	plt.imsave("figs/groundview.png",distances,cmap="inferno")#,aspect=1,extent=(min(phis),max(phis),min(thetas),max(thetas)))
	if "canvas" in viewObjs.keys():		# if this isn't the first time, destroy the old "canvas" object
		viewObjs["canvas"].get_tk_widget().destroy()
		viewObjs["toolbar"].destroy()
	viewObjs["canvas"] = FigureCanvasTkAgg(viewObjs["fig"], master=frameLower)# new canvas object to hold the figure
	viewObjs["toolbar"] = NavigationToolbar2Tk(viewObjs["canvas"],frameLower)	# toolbar, references the canvas
	viewObjs["toolbar"].update()
	viewObjs["canvas"].get_tk_widget().pack(fill='both',expand=True)
	# HANDLE CLICKS
	viewObjs["canvas"].mpl_connect('button_press_event',markPeakOnMapTrigger)

selectedPoints=[[-84.49479385566438, 36.10463278641103], [-84.47737315634767, 36.10851408211372], [-84.47069371723141, 36.11492273315769], [-84.46320191389832, 36.11997744384026], [-84.45832772859727, 36.12846213677172], [-84.45805694052498, 36.14055733733358], [-84.45950114357716, 36.15102780946176]]
route=[]
def calculateRouteFromSelections():
	selected = np.asarray(selectedPoints)
	paths = [ np.asarray(r[:2]) for r in roads ]
	#closests=np.zeros(len(selected)) ; distances = np.zeros(
	#for path in paths: 
	#	print(path.shape)
	#	

def viewLocationTrigger(event):
	#print(dir(event))
	if not hasattr(event,"modifiers"): # old matplotlib may not have .modifiers, so populate from event.key
		event.modifiers = { {"control":"ctrl"}.get(event.key,event.key) } # must remap control/ctrl
	print("em",event.modifiers,"en",event.name,"ek",event.key)
	#mods=[ s for s in event.modifiers ]
	#if "shift" not in event.modifiers:
	#	return
	lon,lat=event.xdata,event.ydata				# lat/lon coords from clicking on the map
	#x=np.argmin(np.absolute(lons-x))			# convert to pixel indices
	#y=np.argmin(np.absolute(lats-y))
	#ys,xs=np.where(elevations==np.nanmax(elevations))
	#x=xs[0] ; y=ys[0] ; print(x,y)
	updateGroundView(lat,lon)					# generate view from the ground from there (rayTrace takes pixel indices
	global mark
	mark[0]=[lon,lat,'r']				# also mark on the map where we were
	updateTopoMap(regen=False)

# TODO FEATURE NOT YET FINISHED. CURRENTLY JUST COLLECTS POINTS
def selectRoadTrigger(event):
	if not hasattr(event,"modifiers"): # old matplotlib may not have .modifiers, so populate from event.key
		event.modifiers = { {"control":"ctrl"}.get(event.key,event.key) } # must remap control/ctrl
	print("em",event.modifiers,"en",event.name,"ek",event.key)
	#mods=[ s for s in event.modifiers ]
	if "ctrl" not in event.modifiers:
		return
	lon,lat=event.xdata,event.ydata				# lat/lon coords from clicking on the map
	print("clicked",lon,lat)
	global selectedPoints
	selectedPoints.append([lon,lat])
	print(selectedPoints)
	calculateRouteFromSelections()
	updateTopoMap(regen=False)

def markPeakOnMapTrigger(event):
	phi,theta=event.xdata,event.ydata			# phi/theta coords from clicking on the ground-view
	p=np.argmin(np.absolute(phis-phi))			# convert to pixel indices
	t=np.argmin(np.absolute(thetas-theta))
	global mark
	j,i=dcoords[t,p,:]					# extract map indices for that point
	#x=int(round(x)) ; y=int(round(y))
	i=int(i) ; j=int(j) 					# reloading npy file may cast to float
	print("i,j,",i,j,"len(lats)",len(lats),"len(lons)",len(lons))
	mark[1]=[lons[i],lats[j],'g']					# mark on the map where we were
	updateTopoMap(regen=False)

setUpButtons()
generateBoth(None,regen=False)

# UNCOMMENT THESE TO DRAW COLOR-CODED BORDERS AROUND EACH FRAME (EG, TO CHECK THAT GRID ELEMENTS EXPAND APPROPRIATELY)
#colors=["red","orange","yellow","green","blue","purple","black"]*10
#for i,frame in enumerate([window,frameLeft,frameRight,frameUpper,frameLower]):
#	frame.configure(highlightbackground=colors[i],highlightthickness=10)

window.mainloop()






