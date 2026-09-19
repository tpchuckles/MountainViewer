# This is copied from genTopo/2025_macbookrestore/rewrite2024.py
import srtm # https://pypi.org/project/SRTM.py/ --> "pip install STRM.py"
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt ; plt.rcParams['figure.dpi'] = 100 ; plt.rcParams['font.size'] = 10
from tqdm import tqdm
#from scipy.interpolate import interp2d
from scipy.interpolate import RectBivariateSpline
import os,json,requests

# lat,long. resolution in x and y
# Gatlinburg Overlook Parking Area #1
#bounds=[[35.751249,-83.540472],[35.578380,-83.333967]] ; resolution=[2000,2000] ; mark=[[35.711249,-83.530472]]
# Knoxville area, testing multiple tile queries
#bounds=[[36.063124,-84.104635],[35.868803,-83.806765]] ; resolution=[3000,3000] ; mark=[[35.958634,-83.990988]]
# Afton Mountain Scenic Overlook
#bounds=[[38.0333108,-78.872453],[37.854108,-78.692240]] ; resolution=[3000,3000] ; mark=[[38.0033108,-78.852453],[37.970131,-78.842867]]
# The entire GSMNP
#bounds=[[35.78,-84.07],		# lat/lon of first corner
#	[35.40,-82.98]]		# lat/lon of opposite corner
#resolution=[100,100]		# target resolution (we'll "smart" adjust this for you if the aspect ratio is off)
#mark=[]

# CONVENTIONS FOR VARIABLE NAMING AND FUNCTION ARGS:
# lat/lon instead of y/x for real-space position. matrices should be lat/lon order (y/x) per convention
# j,i for indices to lat/lon points. nj and ni for sizes (do not use x,y)
# phi,theta are used for real-space angles: phi = azimuthal angle horizontally, theta = angle-above-horizon vertically
# p,t for indices to phi/theta points. np and nt for sizes
# All function arguments and returns should use real-space coordinates (lat/lon if you need to specify a location, we can do an argmin to find the index if we need to. or phi/theta if you need to specify angles)

def main():
	global bounds,datahandler
	bounds=np.asarray(bounds)
	datahandler=srtm.get_data()
	fixBoundsAndResolution(bounds,resolution)
	print(bounds,resolution)
	arry,lats,lons=grid(bounds,resolution,skipInterp=True)
	print(arry,np.shape(arry),np.shape(lats),np.shape(lons))
	#arry[arry==None]=np.nanmin(arry[arry!=None]) # UH OH, IT WE MAY HAVE ENDED UP WITH NONES
	plt.imshow(arry,cmap="inferno",aspect="auto",extent=(min(lons),max(lons),min(lats),max(lats)))
	for m in mark:
		plt.scatter([m[1]],[m[0]],c='r',s=50)
	#plt.show()
	for road in getRoads(bounds):
		#print("road",road)
		lats,lons,name=road
		plt.plot(lons,lats)
		if len(name)>0:
			plt.annotate(name,(lons[0],lats[0]))
	plt.savefig("rewrite2024g.png")
	arry[np.isnan(arry)]=np.nanmin(arry)
	plt.imsave("rewrite2024h.png",arry,cmap="inferno")
	#plt.plot(np.arange(resolution[0]),arry[200,:]) ; plt.show()
	#plt.plot(np.arange(1000),arry[669,:]) ; plt.xlim(660,740) ; plt.ylim(1775,2000) ; plt.show()

	#y=np.argmin(np.absolute(lats[::-1]-mark[0][0])) ; x=np.argmin(np.absolute(lons-mark[0][1]))
	#print(i,j)

	#arry[j,i]=np.amax(arry)
	#plt.clf()
	#plt.imshow(arry,cmap="inferno",aspect="auto",extent=(min(lons),max(lons),min(lats),max(lats))) ; plt.show()

	#rayTracing(arry,((-90,90),(-30,75)),1500,(x,y))
	#rayTracing(arry,((-30,90),(-30,75)),3000,(x,y))

# bounds: [[lat1,lon1],[lat2,lon2]] for two corners
# resolution: [nLonPts,nLatPts]
# this function will update the ordering in bounds to N/W/S/E, and adjust resolution based on real-space aspect ratio
def fixBoundsAndResolution(bounds,resolution):
	N=max(bounds[:,0]) ; S=min(bounds[:,0])
	E=max(bounds[:,1]) ; W=min(bounds[:,1])
	bounds*=0 ; bounds+=np.asarray([[N,W],[S,E]])		# *=0 and += to "in-place" modify the variable
	width=srtm.utils.distance((N+S)/2, E, (N+S)/2, W)	# real-space distance at *center* of frame
	height=srtm.utils.distance(N, (E+W)/2, S, (E+W)/2)	# (since technically a lat/lon box is trapezoidal)
	#print(width,height)
	r=max(resolution)
	if width>=height:
		resolution[0]=r ; resolution[1]=int(round(r*height/width))
	else:
		resolution[1]=r ; resolution[0]=int(round(r*width/height))

# bounds: [[lat1,lon1],[lat2,lon2]] for two corners
# resolution: [nLonPts,nLatPts]
# this function will collect up elevation data on a grid, and returns: 
# elevations: nLatPts x nLonPts 2D matrix of elevation data. (y,x index order, lats *descending*, per imshow convention)
# lats: 1D list of nLatPts. lats are in *descending* order (following "origin in the upper left" imshow convention)
# lons: 1D list of nLonPts
def grid(bounds,resolution,skipInterp=False):
	# OPTION 1: built-in functions. this appears to not do any sort of interpolation (try a high-resolution query and then plotting a slice along one direction)
	#arry=datahandler.get_image(resolution, tuple(bounds[:,0]), tuple(bounds[:,1]),max_elevation=3000,mode="array")
	# OPTION 2: get_image() calls get_elevation() which we can call ourselves, allowing us control of the "approximate" flag. this attempts interpolation, but it isn't that good, and you still get stair-stepping 
	#lats=np.linspace(*bounds[:,0],1000) ; lons=np.linspace(*bounds[:,1],1000)
	#arry=np.zeros((1000,1000))
	#for i,lat in enumerate(tqdm(lats)):
	#	for j,lon in enumerate(lons):
	#		arry[i,j]=datahandler.get_elevation(lat,lon,approximate=True)
	# OPTION 3: find out what file contains the data, query the file to find out where in the file corresponds to our location, then increment row/column in the file, and query lat,lon,elevation for each cell. this effectively gives us an image precisely *at* NASA's resolution (no finer, no courser), which we can then use better tools for interpolation (e.g. scipy's (now-deprecated) interp2d or scipy's RectBivariateSpline). NOTE: WE HAD TO EDIT /home/athena/.local/lib/python3.11/site-packages/srtm/data.py > class GeoElevationFile > get_row_and_column() TO DO A ROUND INSTEAD OF MATH.FLOOR, IF WE WISH TO GRAB ELEVATION BY LAT/LON ASSOCIATED WITH EACH ROW/COL, OTHERWISE FLOORING MAY GIVE US THE WRONG POINTS ELEVATION. (this is also why we found we still needed "approximate=True", because that served to effectively negate the math.floor issue). (and why elev(lat,lon) instead of elev(row,col)? because the former is much easier to handle when moving across multiple tiles (no need to re-set incrementing to zero or whatever)
	tiles = [ datahandler.get_file(*bounds[0]) ] ; tres=tiles[0].resolution
	r0,c0=tiles[0].get_row_and_column(*bounds[0]) # row and column of the upper-left point
	lat0,lon0=tiles[0].get_lat_and_long(r0,c0)
	lats=[] ; lons=[] ; elevs=[]
	for j in range(10000):		# cycle through lats
		elevs.append([])
		for i in range(10000):	# cycle through lons
			#lat,lon=tile.get_lat_and_long(r0+i,c0+j) # row+1 --> longitude incrementing eastward. col+1 --> lattitude decrementing southward
			#r,c=tile.get_row_and_column(lat,lon) ; print(r0+i-r,c0+j-c)
			lat=lat0-j*tres ; lon=lon0+i*tres # origin is N/W (upper/left) corner. next point is down/right
			if j==0:
				lons.append(lon) # on first loop through lons, save off value
			for t in tiles:
				# check if lat,lon is in this file. if not, move to next one
				if (t.latitude <= lat < t.latitude + 1) and (t.longitude <= lon < t.longitude + 1):
					elev=t.get_elevation(lat,lon,approximate=False) # query elevation at this point
					break
			else:	# if no tiles were found with this lat,lon, then read in the new one, and use it
				tiles.append( datahandler.get_file(lat,lon) )
				elev=tiles[-1].get_elevation(lat,lon,approximate=False)
			if elev==None:
				elev=np.nan
			elevs[-1].append(elev)
			if lon>bounds[1,1]:	# once we pass eastern bound, stop cycling i
				break
		lats.append(lat)		# save off lat at end of cycle (since elevs were updated too)
		if lat<bounds[1,0]:		# once we pass southern bound, stop cycling j
			break
	for t in tiles:
		print(t.latitude,t.longitude,t.resolution)
	elevs=np.asarray(elevs)
	#print(len(lats),len(lons),np.shape(elevs))

	if skipInterp:
		return elevs,lats,lons

	# NOW, do 2D interpolation
	elevs=elevs[::-1,:] ; lats=lats[::-1] # "y values must be strictly ascending." lattitudes are ordered north-to-south, so we need to flip them before interpolation
	#f=interp2d(lons,lats,elevs,kind='cubic')
	f=RectBivariateSpline(lons,lats,elevs.T) # takes flipped index order, so transpose elevs
	lats2=np.linspace(*bounds[:,0],resolution[1])[::-1] ; lons2=np.linspace(*bounds[:,1],resolution[0]) # new interp points, including flipped lats
	arry=f(lons2,lats2).T ; arry=arry[::-1,:] # and of course, untranspose output, and flip lats back
	return arry,lats2,lons2

# elevations: nLatPts x nLonPts 2D matrix of elevation data. (y,x index order, lats *descending*, per imshow convention)
# lats: 1D list of nLatPts. lats are in *descending* order (following "origin in the upper left" imshow convention)
# lons: 1D list of nLonPts
# origin: lat/lon pair for where you are standing
# fieldOfView: ((phi1,phi2),(theta1,theta2)). phi is angle about the vertical (0 is east), theta is angle above horizon
# resolution: single integer. we will adjust nphis and nthetas based on aspect ratio
# this function will calculate line-of-sight distances from the viewing point (origin). it returns:
# distances: nThetas x nPhis 2D matrix of distance data (y,x index order, thetas *descending*, per imshow convention)
# phis: 1D list of horizontal angles (0 degrees is East)
# thetas: 1D list of vertical angles. thetas are in *descending* order ("origin in the upper left" imshow convention)
# coords: 3D list of nThetas x nPhis x 2, where the latter two elements store the j,i (lat/lon indices) for each distance
def rayTracing(elevations,lats,lons,origin,fieldOfView,resolution):
	if fieldOfView=="auto": # commenting out because our "distance to straight down" code is fishy
		fov=((0,360),(-89,89))
		dists,phis,thetas,coords=rayTracing(elevations,lats,lons,origin,fov,resolution) # do a course-res scan over all angles
		mask=np.zeros(dists.shape) ; mask[dists>0]=1
		sumsHorizontal=np.sum(mask,axis=1) # we're looking for the lowest angle with no data (all sky)
		#print(sumsHorizontal,dists.shape,len(phis),len(thetas),thetas)
		maxTheta=thetas[ np.where(sumsHorizontal!=0)[0][0]-1 ]	# "first one that has data" (down from the top)
		if max(sumsHorizontal)!=len(phis):
			minTheta=-89
		else:
			minTheta=thetas[ np.where(sumsHorizontal==len(phis))[0][0] ]		# and the "first one that is full of data"
		
		print(minTheta,maxTheta)
		#return rayTracing(elevations,((0,360),(miny,maxy)),resolution,origin)
		j1=np.argmin(np.absolute(thetas-maxTheta)) ; j2=np.argmin(np.absolute(thetas-minTheta))
		return dists[j1:j2],phis,thetas[j1:j2],coords[j1:j2]

	origin_ji=( np.argmin(np.absolute(lats-origin[0])) , np.argmin(np.absolute(lons-origin[1])) )

	((minPhi,maxPhi),(minTheta,maxTheta))=fieldOfView
	if maxPhi-minPhi >= maxTheta-minTheta:
		resPhi=resolution ; resTheta=int(round(resolution*(maxTheta-minTheta)/(maxPhi-minPhi)))
	else:
		resTheta=resolution ; resPhi=int(round(resolution*(maxPhi-minPhi)/(maxTheta-minTheta)))
	print("resPhi",resPhi,"resTheta",resTheta)
	nj,ni=np.shape(elevations)
	# RAY TRACING
	phis=np.linspace(minPhi,maxPhi,resPhi)
	thetas=np.linspace(minTheta,maxTheta,resTheta)[::-1] # reverse thetas. origin is upper-left per imshow convention
	distances=np.zeros((resTheta,resPhi)) ; coords=np.zeros((resTheta,resPhi,2))
	e0=elevations[origin_ji[0],origin_ji[1]]
	for p,phi in enumerate(tqdm(phis)):
		phi=phi%360 ; ESWN="ESWNE"[int(round(phi/360*4))]
		slope=np.tan(phi*np.pi/180) # "for every step in phi, how far do we step in theta"
		#print(aH,ESWN,mH)
		elevationVsDistance=[] ; dists=[]
		if ESWN in "EW":
		#if -1 <= mH <= 1: # "looking east", "rise less than we run", plus or minus rise
			for di in range(ni):
				if ESWN=="W":
					di*=-1
				dj=di*slope
				i=origin_ji[1]+di ; j=int(round(origin_ji[0]+dj))
				#if dx==10 or dx==-10:
				#	print("origin",origin,"x",x,"y",y)
				if i>=ni or j>=nj or i<0 or j<0:
					break
				elevationVsDistance.append( elevations[j,i] ) ; dists.append( (di**2+dj**2)**.5 )
		if ESWN in "SN":
		#if mH>1 or mH<-1: # "looking south", "run less than we rise", plus or minus run
			for dj in range(nj):
				if ESWN=="N":
					dj*=-1
				di=dj/slope
				i=int(round(origin_ji[1]+di)) ; j=origin_ji[0]+dj
				#if dy==10 or dy==-10:
				#	print("origin",origin,"x",x,"y",y)
				if i>=ni or j>=nj or i<0 or j<0:
					break
				elevationVsDistance.append( elevations[j,i] ) ; dists.append( (di**2+dj**2)**.5 )
		#if aH>45:
		#	plt.plot(dists,elevationVsDistance) ; plt.show()
		
		angleToEachPoint=[ np.arctan2( e-(e0+10) , d )*180/np.pi for e,d in zip(elevationVsDistance,dists) ]
		i=np.argmin(elevationVsDistance) # the lowest point
		#if aH>45:
		#	plt.plot(dists[i:],angleToEachPoint[i:]) ; plt.show()
		angleToEachPoint=np.asarray(angleToEachPoint) ; dists=np.asarray(dists)
		#print("e0",e0)
		#print("elevs",elevationVsDistance[:10])
		#print("dist ",dists[:10])
		#print("angle",angleToEachPoint[:10])

		for t,theta in enumerate(thetas):# find the "first point" on the angle-vs-distance plot where line crosses this y-value
			# scan from the lowest point, outwards? this doesn't seem right
			#js=[ j for j in range(i,len(angleToEachPoint)-1) if angleToEachPoint[j]<aV<=angleToEachPoint[j+1] ]
			#plt.plot(dists[i:],angleToEachPoint[i:]) ; plt.scatter(dists[js],angleToEachPoint[js]) ; plt.show()
			#'-.     .       	line of sight follows aV, we're looking for a point where 
			#    '-./ \    .	angleToEachPoint is just below, then immediately above, aV
			#      / '-\. / \	(this would be upwards-sloping ground, which passes through
			#     /     \/'-.	our line of sight, aV)
			ns=[ n for n in range(0,len(angleToEachPoint)-1) if angleToEachPoint[n]<theta<=angleToEachPoint[n+1] ]
			if len(ns)==0:
				distances[t,p]=0 ; coords[t,p,:]=0
			else:
				distances[t,p]=dists[ns[0]]+1
				coords[t,p,1]=int(round(origin_ji[1]+dists[ns[0]]*np.cos(phi*np.pi/180)))
				coords[t,p,0]=int(round(origin_ji[0]+dists[ns[0]]*np.sin(phi*np.pi/180)))
			#print("aV",aV,"e0",e0)
			#print("elevs",elevationVsDistance[:6])
			#print("dist ",dists[:6])
			#print("angle",angleToEachPoint[:6])
			#print("js   ",js[:6])


	#distances=distances[::-1] # we're looping through increasing angles, rastering "up" the mountains, so reverse in Y for imshow (+y is down)
	#thetas=thetas[::-1] # (also flip anglesVertical so the indices are correct)
	#coords=coords[::-1]
	#plt.imshow(distances,cmap="inferno",aspect="auto",extent=(xmin,xmax,ymin,ymax)) ; plt.show()
	#distances[distances==np.nan]=np.nanmin(distances)
	#plt.imsave("figs/rayTracing.png",distances,cmap="inferno")
	return distances,phis,thetas,coords

def getRoads(bounds):
	roads = []
	(lat0,lon0),(latf,lonf)=bounds
	lat0,latf=min(lat0,latf),max(lat0,latf)
	lon0,lonf=min(lon0,lonf),max(lon0,lonf)
	# DUMMY SINUSOID ROADS JUST TO MAKE SURE WE'RE HANDLING BOUNDS AND PLOTTING PROPERLY
	#sx=lonf-lon0 ; sy=latf-lat0
	#for i in range(0,20,2):
	#	lons = np.linspace(lon0+sx/20*i,lon0+sx/20*(i+1),30)
	#	lats = np.linspace(lat0+sy/20*i,lat0+sy/20*(i+1),30)
	#	lats += sy/10*np.sin(lons/(sx/20)*2*np.pi)
	#	roads.append([lats,lons])
	# QUERYING OR RELOADING
	jfile=str(lat0)+","+str(lon0)+"-"+str(latf)+","+str(lonf)+".json"
	if os.path.exists(jfile):
		with open(jfile,'r') as infile:
			jdata = json.load(infile)
	else:
		print("QUERYING OSM DATA")
		overpass_url = "https://overpass-api.de/api/interpreter"
		overpass_query="[out:json][timeout:25];(" # overpass query processing time-out. too high and query may be rejected, too low and the alotted time may not be enough depending on the size of our query
		overpass_query=overpass_query+"way[\"highway\"]("+str(lat0)+","+str(lon0)+","+str(latf)+","+str(lonf)+");"
		overpass_query=overpass_query+");(._;>;);out center;"
		#https://towardsdatascience.com/loading-data-from-openstreetmap-with-python-and-the-overpass-api-513882a27fd0
		response = requests.post(overpass_url,
						   data={'data': overpass_query},
						   headers={"User-Agent": "github.com/tpchuckles/genTopo/","Accept": "application/json"},
						   timeout=(10,85)) # http post timeouts: connection timeout, and read timeout (not just 10+25, but additional 60s buffer, to allow for queuing delay with overpass)
		print(overpass_query,response)
		jdata = response.json()
		with open(jfile, 'w') as outfile: #https://stackabuse.com/reading-and-writing-json-to-a-file-in-python/
			json.dump(jdata, outfile)
	# PARSING: ways are stored as ordered lists of nodes. nodes contain the lat/lon coordinates.
	nodes={} # first parse out all the nodes:
	for e in jdata["elements"]:
		if e["type"]=="node":
			ID=e["id"] ; lat=e["lat"] ; lon=e["lon"]
			nodes[ID]=(lat,lon)
	#print(nodes)
	for e in jdata["elements"]:
		if e["type"]=="way":
			roads.append([[],[],""])		# new road
			ID=e["id"]
			for n in e["nodes"]:		# loop through nodes...
				lat,lon=nodes[n]	# this way's this node's lat/lon
				if lat<lat0 or lat>latf or lon<lon0 or lon>lonf:
					continue	# exclude out-of-bounds
				roads[-1][0].append(lat)
				roads[-1][1].append(lon)
			tags=e.get("tags",{})
			if "name" in tags.keys():
				roads[-1][2]=tags["name"]
				#print("name",tags["name"])
	return roads

def setGlo(paramName,value):
	globals()[paramName]=value

def getGlo(paramName):
	return globals()[paramName]

if __name__=='__main__':
	main()
