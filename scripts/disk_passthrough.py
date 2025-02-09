#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Name: disk_passthrough.py
# Description:
#   This script assists in passing through physical disks to Proxmox VMs.
#   It enumerates all available physical disks on the host (excluding those
#   used in ZFS pools) and lists all VMs. The user can then select which 
#   disks and VM they would like to pass through. The script will generate 
#   the corresponding Proxmox 'qm set' commands that can be used to assign 
#   these disks directly to the selected VM.
#
# Usage:
#   1. Run the script on a Proxmox host.
#   2. Choose disks from the enumerated list.
#   3. Choose the target VM.
#   4. The script will output the commands needed to pass through the 
#      selected disks to the chosen VM.
#
# Requirements:
#   - Must be run on a Proxmox host with 'qm' and 'zpool' commands 
#     available.
#   - Python 3.x
#   - Sufficient privileges to run 'lsblk', 'zpool', and 'qm' commands.
#
# Note:
#   - This script does not automatically apply changes; it only generates 
#     the necessary commands. Users should carefully review the output 
#     before running the commands.
#   - Use at your own risk. Ensure you have proper backups and understand 
#     the implications of passing through disks to a VM.
#
# Author:
#   Pedro Anisio Silva / ARC4D3
#
# License:
#   This script is provided "as is", without warranty of any kind, express 
#   or implied. You are free to modify and distribute this script as you 
#   wish, but the author takes no responsibility for any potential harm, 
#   data loss, or damage caused by its use.
#

import subprocess
import logging
import re

logging.basicConfig(level=logging.INFO)

def enumerate_physical_disks():
    """
    Enumerates physical disks on the host, excluding ZFS pool disks.
    :return: List of dictionaries representing physical disks.
    """
    try:
        output = subprocess.check_output(["lsblk", "-d", "-o", "NAME,MODEL,SERIAL,SIZE"], text=True)
        output = re.sub(r'([a-zA-Z]) ([a-zA-Z])', r'\1-\2', output) # Replace single spaces surrounded by letters with hyphen (for disk models)
        print( "lsblk -d -o NAME,MODEL,SERIAL,SIZE") #DEBUG
        zfs_disks_output = subprocess.check_output(["zpool", "status"], text=True).split("\n")
        zfs_disk_names = {line.split()[0] for line in zfs_disks_output if "ONLINE" in line}

        lines = output.strip().split("\n")[1:]  # Skip the header line
        disks = []
        for line in lines:
            parts = line.split(maxsplit=3)
            if len(parts) == 4 and all(parts) and parts[0] not in zfs_disk_names:
                # Find the first matching /dev/disk/by-id path
                print(f"find /dev/disk-by-id/ -lname {parts[0]}") #DEBUG
                id_paths = subprocess.check_output(
                    ["find", "/dev/disk/by-id/", "-lname", f"*{parts[0]}"],
                    text=True,
                ).splitlines()
                if id_paths:
                    print("Found id_paths")   #DEBUG
                    # Prioritize `wwn-*` over `ata-*` if both exist
                    prioritized_path = next((p for p in id_paths if "wwn-" in p), id_paths[0])
                    #disks.append({"name": parts[0], "model": parts[1], "size": parts[2], "id_path": prioritized_path})
                    disks.append({"name": parts[0], "model": parts[1], "serial": parts[2], "size": parts[3], "id_path": prioritized_path})
        return disks
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing lsblk or zpool commands: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return []

def list_vms():
    """
    Lists all VMs on the host.
    :return: List of dictionaries representing VMs.
    """
    try:
        output = subprocess.check_output(["qm", "list"], text=True)
        lines = output.strip().split("\n")[1:]  # Skip the header line
        
        vms = []
        for line in lines:
            parts = line.split(maxsplit=2)
            if len(parts) == 3:
                vms.append({
                    "vmid": int(parts[0]),
                    "name": parts[1],
                    "status": parts[2]
                })
        return vms
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing qm list: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return []

def get_used_scsi_indexes(vmid):
    """
    Retrieves used SCSI indexes for the specified VM.
    :param vmid: ID of the VM.
    :return: Set of used SCSI indexes.
    """
    try:
        output = subprocess.check_output(["qm", "config", str(vmid)], text=True)
        scsi_indexes = set()
        for line in output.splitlines():
            match = re.match(r"scsi(\d+):", line)
            if match:
                scsi_indexes.add(int(match.group(1)))
        return scsi_indexes
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving VM configuration: {e}")
        return set()

def generate_passthrough_commands(selected_disks, selected_vm):
    """
    Generates passthrough commands for the selected disks and VM.
    Ensures no overlapping SCSI indexes.
    :return: List of passthrough commands.
    """
    commands = []
    vmid = selected_vm["vmid"]
    used_indexes = get_used_scsi_indexes(vmid)
    scsi_index = 0  # Start with the first SCSI index

    for disk in selected_disks:
        while scsi_index in used_indexes:
            scsi_index += 1  # Find the next available index
        commands.append(f"qm set {vmid} -scsi{scsi_index} {disk['id_path']}")
        used_indexes.add(scsi_index)  # Mark this index as used
    return commands

def validate_disk_selection(selected_disks, available_disks):
    """
    Validates if the selected disks exist in the list of available disks.
    :return: True if all disks are valid, False otherwise.
    """
    for selected_disk in selected_disks:
        if not any(
            disk["name"] == selected_disk["name"] and
            disk["model"] == selected_disk["model"] and
            disk["serial"] == selected_disk["serial"] and
            disk["size"] == selected_disk["size"]
            for disk in available_disks
        ):
            return False
    return True

def validate_vm_selection(selected_vm, available_vms):
    """
    Validates if the selected VM exists in the list of available VMs.
    :return: True if valid, False otherwise.
    """
    for vm in available_vms:
        if (
            vm["vmid"] == selected_vm["vmid"] and
            vm["name"] == selected_vm["name"] and
            vm["status"] == selected_vm["status"]
        ):
            return True
    return False

def main():
    """
    Entry point for running the script.
    """
    print("Enumerating physical disks...")
    disks = enumerate_physical_disks()
    if not disks:
        print("No physical disks available.")
        return
    for i, disk in enumerate(disks, 1):
        print(f"[{i}] {disk}")

    try:
        selected_indexes = input("Select disk indexes (comma-separated): ").split(",")
        selected_disks = [disks[int(index.strip()) - 1] for index in selected_indexes]
    except (IndexError, ValueError):
        print("Invalid disk selection. Exiting.")
        return

    print("\nListing VMs...")
    vms = list_vms()
    if not vms:
        print("No VMs found.")
        return
    for i, vm in enumerate(vms, 1):
        print(f"[{i}] {vm}")

    try:
        selected_vm = vms[int(input("Select a VM index: ")) - 1]
    except (IndexError, ValueError):
        print("Invalid VM selection. Exiting.")
        return

    print("\nValidating passthrough feasibility...")
    if not validate_disk_selection(selected_disks, disks):
        print("One or more selected disks are invalid.")
        return
    if not validate_vm_selection(selected_vm, vms):
        print("Selected VM is invalid.")
        return

    print("\nGenerating passthrough commands...")
    commands = generate_passthrough_commands(selected_disks, selected_vm)
    print("\nGenerated Commands:")
    for cmd in commands:
        print(cmd)

if __name__ == "__main__":
    main()
