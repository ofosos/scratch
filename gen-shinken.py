#!/usr/bin/env python2

import random
from jinja2 import Template

wordlist = "wordlist.shinken"

host_template = Template("""define host {
  host_name {{ host }}
  alias The Bogus Host {{ host }}
  hostgroups {{ hostgroup }}
  address 127.0.0.1
  check_command check_dummy!0!Very well
  check_interval 5
  retry_interval 1
  max_check_attempts 5
  check_period 24x7
  process_perf_data 0
  retain_nonstatus_information 0
  contact_groups admins
  notification_interval 3600
  notification_period none
  notification_options 
}

""")

service_template = Template("""define service {
  host_name {{ host }}
  service_description {{ service }}
  check_command check_dummy!0!Very well
  max_check_attempts 5
  check_interval 5
  retry_interval 1
  check_period 24x7
  notification_interval 3600
  notification_period none
  contact_groups admins
}

""")

hostgroup_template = Template("""define hostgroup {
  hostgroup_name {{ hostgroup }}
  alias The bogus hostgroup {{ hostgroup }}
}

""")

words = [ x.rstrip() for x in open(wordlist) ]

hostgroups = random.sample(words, 40)

for hostgroup in hostgroups:
    print hostgroup_template.render(hostgroup=hostgroup)

    hosts = random.sample(words, 10)

    for host in hosts:
        print host_template.render(hostgroup=hostgroup, host=host)

        services = random.sample(words, 2)

        for service in services:
            print service_template.render(host=host, service=service)


