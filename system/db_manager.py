import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from system.database import DBManager
except ImportError:
    try:
        from .database import DBManager
    except ImportError:
        from database import DBManager
