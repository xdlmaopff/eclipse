import asyncio
import os
import sys
import importlib.util

async def run_custom_script(script_code: str, params: dict, session_path: str):
    """Run custom Python script"""
    try:
        # Create temp script file
        script_path = f"temp_script_{hash(script_code)}.py"
        with open(script_path, "w") as f:
            f.write(script_code)

        # Load and execute
        spec = importlib.util.spec_from_file_location("custom_script", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Assume script has async run function
        if hasattr(module, 'run'):
            await module.run(session_path, params)

        # Cleanup
        os.remove(script_path)
        return True
    except Exception as e:
        print(f"Custom script error: {e}")
        return False