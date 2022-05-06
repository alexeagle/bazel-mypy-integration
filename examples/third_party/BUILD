load("@my_deps//:requirements.bzl", "requirement")

py_binary(
    name = "main",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        requirement("types_python_dateutil"),  # this doesn't avoid 'Library stubs not installed for "dateutil"'
    ],
)
