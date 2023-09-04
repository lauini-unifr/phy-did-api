"""
blocklist.py

This file contains the blocklist of the JWT tokens. It will be imported by app and the logout ressource so that tokens can be added to the blocklist when the user logs out.
"""

BLOCKLIST = set()