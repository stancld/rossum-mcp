uv-lock:
	rm uv.lock && uv lock;
	cd rossum-agent && rm uv.lock && uv lock && cd ..;
	cd rossum-deploy && rm uv.lock && uv lock && cd ..;
	cd rossum-mcp && rm uv.lock && uv lock && cd ..;
