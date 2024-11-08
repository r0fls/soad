{
  description = "Python development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        pythonEnv = pkgs.python3.withPackages (ps: with ps; [ pip virtualenv ]);

        pipRequirements = pkgs.writeText "requirements.txt" ''
          tastytrade==8.3
          pytest==8.3.3
          pytest-asyncio==0.24.0
          requests-oauthlib
          sqlalchemy
          pyyaml
          flask
          flask-cors
          flask-jwt-extended
          python-json-logger
          pytz
          numpy
          scipy
          asyncpg
          psycopg2-binary
          websocket-client
          yfinance
          freezegun
          aiosqlite
          greenlet
          python-dotenv
          aiohttp
        '';

      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.stdenv.cc.cc.lib # Add libstdc++
            pkgs.zlib
            pkgs.glib
          ];

          shellHook = ''
            # Create and activate a virtual environment if it doesn't exist
            VENV=.venv
            if test ! -d $VENV; then
              echo "Creating virtual environment..."
              ${pythonEnv}/bin/python -m venv $VENV
            fi

            # Always recreate activation script to ensure paths are correct
            ${pythonEnv}/bin/python -m venv $VENV

            # Activate the virtual environment
            source ./$VENV/bin/activate

            # Ensure pip is up to date in the venv
            python -m pip install --upgrade pip

            # Install pip requirements
            echo "Installing pip packages..."
            pip install -r ${pipRequirements}

            # Export PYTHONPATH to include the project root
            export PYTHONPATH="$PWD:$PYTHONPATH"

            # Ensure virtualenv's bin directory is first in PATH
            export PATH="$PWD/.venv/bin:$PATH"

            # Add library path for libstdc++ and other system libraries
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:${pkgs.glib}/lib:$LD_LIBRARY_PATH"
          '';
        };
      });
}
