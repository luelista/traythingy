{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    #pinboard.url = "/home/mira/Repos/miau/pinboard-next/connectors/python";
    pinboard = {
      type = "git";
      url = "ssh://git@github.com/luelista/pinboard.git";
      dir = "connectors/python";
    };
    #pinboard.url = "git+ssh://git@github.com/luelista/pinboard.git?dir=connectors";
    pinboard.inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = { self, nixpkgs, pinboard, ... }: {
    packages.x86_64-linux = let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
      };
    in {
      traythingy = pkgs.python3Packages.buildPythonApplication {
        pname = "traythingy";
        version = "0.0.1";
        pyproject = true;

        src = ./.;

        nativeBuildInputs = [
          pkgs.qt5.wrapQtAppsHook
          pkgs.python3Packages.setuptools
          pkgs.copyDesktopItems
        ];
        propagatedBuildInputs = [
          pkgs.python3Packages.pyqt5
          pkgs.python3Packages.qscintilla
          pkgs.libsForQt5.qtbase
          pkgs.python3Packages.qasync
          pinboard.packages.x86_64-linux.python-easyrpc
        ];

        preFixup = ''
          makeWrapperArgs+=("''${qtWrapperArgs[@]}")
        '';

        desktopItems = [
          (pkgs.makeDesktopItem {
            name = "traythingy";
            desktopName = "Traythingy";
            exec = "traythingy";
          })
        ];

      };

      default = self.packages.x86_64-linux.traythingy;
    };
  };
}
