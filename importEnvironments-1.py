import getopt, sys, time, ast, sets, re
import csv


DEBUG = 1
helpMessage = 'cli.sh -host <XLDeployHost> -username <username> -password <password> -f $PWD/importEnvironment -- -e <envs.csv> -x <extraProperties>'
importLocation = 'tda-import'
commandLineProps = None
def get_val(key, dic):
    keys = dic.keys()
    key = key.lower().replace(' ','')
    for k in keys:
        long_key = k
        k = k.lower().replace(' ', '')
        if k == key:
            return dic[long_key]

def parseCSVFile(csvFile):
    envsMap = {}
    with open(csvFile, 'rb') as fin:
        csv_r = csv.DictReader(fin, delimiter=',')
        rows = csv_r
        for row in rows:
            serverName = get_val('serverName',row)
            fqdn = get_val('centrifyDomain',row)
            instanceName = get_val('instanceName',row)
            subSystems = get_val('subSystems', row)
            applicationName = get_val('SCMApplicationName', row)

            propertiesMap = {}
            propertiesMap['serverName'] = serverName
            propertiesMap['fqdn'] = fqdn
            propertiesMap['instanceName'] = instanceName
            propertiesMap['subSystems'] = subSystems
            propertiesMap['applicationName'] = applicationName
            envsMap[serverName] = propertiesMap

    return envsMap

def newUnixHost(path, name, address, tags):
    global commandLineProps
    if 'password' in commandLineProps:
        password = commandLineProps['password']
    else:
        password = ''

    host_param = {
                'address': address,
                'os':'UNIX',
                'connectionType':'SUDO',
                'username': 'Zdeploy',
                'password': password,
                'temporaryDirectoryPath': '/tmp',
                'stagingDirectoryPath': '/tmp',
                'tags': tags,
                'sudoUsername': 'tomcat',
                'suUsername': 'tomcat'
            }


    m = re.search(r'(PROD|DR)\-(\w\w)',path)
    if m:
        location = m.group(2)

        if location.lower() == 'tx':
            host_param['jumpstation'] = 'Infrastructure/jumpstation/tx-jumpstation'
        elif location.lower() == 'ct':
            host_param['jumpstation'] = 'Infrastructure/jumpstation/ct-jumpstation'
        elif location.lower() == 'jc':
            host_param['jumpstation'] = 'Infrastructure/jumpstation/jc-jumpstation'

    print host_param

    unixHost = factory.configurationItem(
            path + '/' + str(name),
            'overthere.SshHost',host_param
        )
    if not repository.exists(unixHost.id):
        print "Creating Unix server: " + str(name)
        return repository.create(unixHost)
    else:
        return repository.read(unixHost.id)

def readCi(id):
    try:
        return repository.read(id)
    except:
        return None    

def newDict(name, entries):
    return repository.create(factory.configurationItem('Environments/' + importLocation + '/' + name, 'udm.Dictionary', {'entries': entries}))

def newTcServer(name, subsystem, host, tomcatHome):
    print "creating TcServer: " + name + " on host " + str(host)

    startCommand = tomcatHome + 'bin/tcruntime-ctl.sh start > /dev/null'
    stopCommand = tomcatHome + 'bin/tcruntime-ctl.sh stop > /dev/null'
    statusCommand = 'netstat -na | grep 8080 | grep -q LISTEN'
    tags = []
    if isinstance(subsystem, list):
        tags = subsystem
    elif isinstance(subsystem, basestring):
        tags = subsystem.split(',')
    tcServer = factory.configurationItem(host.id + '/' + name, 'tomcat.Server',
        {
        'host': host.id,
        'home': tomcatHome,
        'startCommand': startCommand,
        'stopCommand': stopCommand,
        'statusCommand': statusCommand,
        'startWaitTime': 5,
        'stopWaitTime': 5,
        'tags': tags
        })
    if not repository.exists(tcServer.id):
        print "Creating tomcat server: " + str(name)
        #print "Deleting tomcat server: " + str(name)
        #repository.delete(tcServer.id)
        return repository.create(tcServer)
    else:
        return repository.update(tcServer)


def newVirtualHost(name, applicationName, tcServer, subsystem, host):   #defining virtualHost on the infrastructure 
    print "creating Tomcat VirtualHost: " + name + " on host " + str(host) # give the print statement 

    tomcatHome = '/app/tomcat/' + applicationName

    startCommand = tomcatHome + '/bin/tcruntime-ctl.sh start > /dev/null'
    stopCommand = tomcatHome + '/bin/tcruntime-ctl.sh stop > /dev/null'
    restartCommand = tomcatHome + '/bin/tcruntime-ctl.sh stop > /dev/null'
    statusCommand = 'netstat -na | grep 8080 | grep -q LISTEN'
    tags = []
    if isinstance(subsystem, list):
        tags = subsystem
    elif isinstance(subsystem, basestring):
        tags = subsystem.split(',')
    i=0                      # tags in upper case 
    for tag in tags:
        tags[i]=tag.upper()

    tcVirtualHost = factory.configurationItem(tcServer.id + '/' + name, 'tomcat.VirtualHost',
        {
        'stopStartRestartConnection': host.id,
        'server': tcServer.id,
        'hostName': 'localhost',
        'appBase': 'webapps',
        'startScript': startCommand,
        'stopScript': stopCommand,
        'restartScript': restartCommand,
        'tags': tags
        })
    if not repository.exists(tcVirtualHost.id):
        print "Creating Tomcat VirtualHost: " + str(name)
        return repository.create(tcVirtualHost)
    else:
        return repository.update(tcVirtualHost)


def newDirectoryIfNotExists(path):
    directory = factory.configurationItem(path, "core.Directory")
    print 'ID: ' + directory.id
    if not repository.exists(directory.id):
        print "creating directory: " + str(directory)
        repository.create(directory)

def run():
    global importLocation
    global environmentsFile
    vals = parseCSVFile(environmentsFile)

    for val in vals:
        print "Processing: " + val
        serverName = get_val('serverName', vals[val])
        instanceNames = get_val('instanceName', vals[val])
        fqdn = get_val('fqdn', vals[val])
        subSystems = get_val('subSystems', vals[val])
        fullQualifiedServername = serverName + '.' + fqdn
        applicationName = get_val('applicationName', vals[val])

        infraRootDir = 'Infrastructure/' + importLocation
        newDirectoryIfNotExists(infraRootDir)

        m =  re.match(r'^(.+?)lv.+?(\d\d)$',serverName)
        if m:
            shortname = m.group(1)
            if re.match(r'^(.+?)(\d\d)$',shortname):
                m = re.match(r'^(.+?)(\d\d)$',shortname)
                newImportLocation = m.group(1)+str(int(m.group(2)))
                newImportLocation = newImportLocation.upper()
                infraRootDir = 'Infrastructure/' + importLocation + '/' + newImportLocation
                newDirectoryIfNotExists(infraRootDir)
            else:
                m = re.match(r'(\w{2,3})(\w\w)',shortname)
                if m:
                    server_type = m.group(1)
                    server_loc = m.group(2)
                    if 'prd' in server_type.lower():
                        if server_loc.lower() in ['jc','mw']:
                            dir_name = 'DR-' + server_loc.upper()
                        else:
                            dir_name = 'PROD-'+server_loc.upper()
                    elif 'bet' in server_type.lower():
                        dir_name = 'BETA-' + server_loc.upper()
                    elif 'bet' in server_type.lower():
                        dir_name = 'BETA-' + server_loc.upper()
                    elif 'dr' in server_type.lower():
                        dir_name = 'DR-' + server_loc.upper()
                    elif 'dev' in server_type.lower():
                        dir_name = 'DEV'
                    elif 'pte' in server_type.lower():
                        dir_name = 'PTE'
                    else:
                        dir_name = shortname.upper()

                    newImportLocation = dir_name
                    newImportLocation = newImportLocation.upper()
                    infraRootDir = 'Infrastructure/' + importLocation + '/' + newImportLocation
                    newDirectoryIfNotExists(infraRootDir)

        infraRootDir = 'Infrastructure/' + importLocation + '/' + newImportLocation + '/' + applicationName
        newDirectoryIfNotExists(infraRootDir)

        host = newUnixHost(infraRootDir, serverName, fullQualifiedServername, [])
        instanceNames = [x.strip() for x in instanceNames.split(',')]
        subSystems = [x.strip() for x in subSystems.split(',')]
        i = 0
        if len(instanceNames) == 1:
            for subsystem in subSystems:
                tcname = 'tcserver_' + instanceNames[0]
                tomcatHome = '/app/tomcat/' + instanceNames[0] + '/'
                tcServer = newTcServer(tcname, subSystems, host, tomcatHome)
                vmName = instanceNames[0].lower() + '_' + serverName
                newVirtualHost(vmName, subsystem, tcServer, subSystems, host)
        elif len(instanceNames) > 1:
            for instanceName in instanceNames:
                tcname = 'tcserver_' + instanceName
                tomcatHome = '/app/tomcat/' + instanceName + '/'
                tcServer = newTcServer(tcname, subSystems[i], host, tomcatHome)
                vmName = instanceName+ '_' +serverName
                newVirtualHost(vmName,subSystems[i],tcServer,subSystems[i],host)
                i += 1
        else:
            print 'No instance found.'

    print "Done creating basic infra"


def env_run():  ## adding the environment section 
    depApp = repository.search("tomcat.VirtualHost")
    vhostlist = {}
    for ci in depApp:
        print ci
        m = re.search(r'/((PR|DR|DEV|BETA|PTE|STE).*?)/',ci,re.IGNORECASE)
        if m:
            env_id = m.group(1)
            if env_id not in vhostlist:
                vhostlist[env_id] = []
            vhostlist[env_id].append(ci)
    for vhost in vhostlist:
        envdir = factory.configurationItem('Environments/'+vhost, "core.Directory")
        repository.create(envdir)
        env = factory.configurationItem('Environments/'+vhost+'/'+vhost, 'udm.Environment')
        env.values['members'] = vhostlist[vhost]
        repository.create(env)

# vars
environmentsFile = None

# Parse out the arguments
try:
    opts, args = getopt.getopt(sys.argv[1:],'he:nx:',['environmentsFile='])
except getopt.GetoptError:
    print helpMessage
    sys.exit(2)
for opt, arg in opts:
    if opt == '-h':
        print helpMessage
        sys.exit(-1)
    elif opt in ('-e', '--environmentsFile'):
        environmentsFile = arg
    elif opt in ('-x', '--extraProperties'):
        commandLineProps = ast.literal_eval(arg)

if environmentsFile == None: 
    print helpMessage
else:
    #print commandLineProps
    run()
    env_run()