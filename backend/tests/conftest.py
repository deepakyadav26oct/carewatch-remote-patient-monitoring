import os, sys, tempfile
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["SIMULATE"] = "false"
os.environ["SIMULATOR_KEY"] = "test-key"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
