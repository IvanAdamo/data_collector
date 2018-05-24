"""Command line application that gives back the most recent value of a SARAD
instrument whenever it is called.
Made to be a data source for Zabbix agent."""

import SarI
import click
import pickle
from filelock import Timeout, FileLock
from pyzabbix import ZabbixMetric, ZabbixSender
import time

@click.group()
def cli():
    """Description for the group of commands"""
    pass

@cli.command()
@click.option('--instrument', default=0, type=click.IntRange(0, 255), help='Instrument Id')
@click.option('--component', default=0, type=click.IntRange(0, 63), help='The Id of the sensor component.')
@click.option('--sensor', default=0, type=click.IntRange(0, 255), help='The Id of the sensor of the component.')
@click.option('--measurand', default=0, type=click.IntRange(0, 3), help='The Id of the measurand of the sensor.')
@click.option('--path', type=click.Path(writable=True), default='mycluster.pickle', help='The path and file name to cache the cluster in a Python Pickle file.')
@click.option('--lock_path', type=click.Path(writable=True), default='mycluster.lock', help='The path and file name of the lock file.')
def value(instrument, component, sensor, measurand, path, lock_path):
    """Command line application that gives back the most recent value of a SARAD
    instrument whenever it is called.
    Made to be a data source for Zabbix agent."""
    lock = FileLock(lock_path)
    try:
        with lock.acquire(timeout=10):
            try:
                with open(path, 'rb') as f:
                    mycluster = pickle.load(f)
            except:
                mycluster = SarI.SaradCluster()
            print(mycluster.connected_instruments[instrument].\
                  get_recent_value(\
                                   component,\
                                   sensor,\
                                   measurand\
                  )['value'])
            with open(path, 'wb') as f:
                pickle.dump(mycluster, f, pickle.HIGHEST_PROTOCOL)
    except Timeout:
        print("Another instance of this application currently holds the lock.")

@cli.command()
def cluster():
    """Show list of connected SARAD instruments."""
    mycluster = SarI.SaradCluster()
    for connected_instrument in mycluster.connected_instruments:
        print(connected_instrument)
        print()

def send_trap(component_mapping, host, instrument, sensor, measurand, zbx, path, lock):
    try:
        metrics = []
        with lock.acquire(timeout=10):
            try:
                with open(path, 'rb') as f:
                    mycluster = pickle.load(f)
            except:
                mycluster = SarI.SaradCluster()
            for component_map in component_mapping:
                value = mycluster.connected_instruments[instrument].\
                      get_recent_value(\
                                       component_map['id'],\
                                       sensor,\
                                       measurand\
                      )['value']
                key = component_map['name']
                metrics.append(ZabbixMetric(host, key, value))
            zbx.send(metrics)
            with open(path, 'wb') as f:
                pickle.dump(mycluster, f, pickle.HIGHEST_PROTOCOL)
    except Timeout:
        print("Another instance of this application currently holds the lock.")

@cli.command()
@click.option('--instrument', default=0, type=click.IntRange(0, 255), help='Instrument Id')
@click.option('--host', default='localhost', type=click.STRING, help='Host name as defined in Zabbix')
@click.option('--server', default='127.0.0.1', type=click.STRING, help='Server IP address or name')
@click.option('--path', default='mycluster.pickle', type=click.Path(writable=True), help='The path and file name to cache the cluster in a Python Pickle file.')
@click.option('--lock_path', default='mycluster.lock', type=click.Path(writable=True), help='The path and file name of the lock file.')
@click.option('--period', default=60, type=click.IntRange(30, 7200), help='Time interval in seconds for the periodic retrieval of values.  Use CTRL+C to stop the program.')
@click.option('--once', is_flag=True, help='Retrieve only one set of data.')
def trapper(instrument, host, server, path, lock_path, once, period):
    """Start a Zabbix trapper service to provide all values from an instrument."""
    component_mapping = [
        dict(id = 0, name = 'radon'),
        dict(id = 1, name = 'thoron'),
        dict(id = 2, name = 'temperature'),
        dict(id = 3, name = 'humidity'),
        dict(id = 4, name = 'pressure'),
    ]
    sensor = 0
    measurand = 0
    zbx = ZabbixSender(server)
    lock = FileLock(lock_path)
    starttime = time.time()
    while not once:
        send_trap(component_mapping, host, instrument, sensor, measurand, zbx, path, lock)
        time.sleep(period - time.time() % period)
    send_trap(component_mapping, host, instrument, sensor, measurand, zbx, path, lock)
