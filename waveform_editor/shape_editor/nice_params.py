import param


class BaseParams(param.Parameterized):
    def reset(self):
        for p in self.param:
            attr = getattr(self, p)
            if p == "name":
                continue
            elif hasattr(attr, "reset"):
                attr.reset()
            else:
                setattr(self, p, self.param[p].default)


# class ShapeParams(BaseParams):
#     parametric_bnd = param.Boolean(default=True)
#     a = param.Number(default=1.9, bounds=(0, 5))
#     center_r = param.Number(default=6.2, bounds=(5, 7.5))
#     center_z = param.Number(default=0.545, bounds=(0, 2))
#     kappa = param.Number(default=1.8, bounds=(0, 5))
#     delta = param.Number(default=0.43, bounds=(0, 5))
#     rx = param.Number(default=5.089, bounds=(0, 10))
#     zx = param.Number(default=-3.346, bounds=(-10, 0))
#     n_desired_nice_bnd_points = param.Integer(default=96, bounds=(1, 200))
#


class NiceParams(BaseParams):
    # global parameters
    time = param.Number(default=249.5)
    mode = param.Selector(default="Static Inverse", objects=["Static Inverse"])
    iterMaxInv = param.Integer(
        default=40, bounds=(1, 100), label="Max number of iterations"
    )
    epsStopInv = param.Number(
        default=1.0e-10,
        bounds=(1e-20, 1e-5),
        label="Tolerance",
    )

    # p' and ff' parameters
    useInputAB = param.Boolean(default=True)
    Aabg = param.String(default="2, 0.6, 1.4")
    Babg = param.String(default="2, 0.4, 1.4")

    # shape params
    # shape_params = param.ClassSelector(class_=ShapeParams, default=ShapeParams())
    parametric_bnd = param.Boolean(default=True)
    a = param.Number(default=1.9, bounds=(0, 5))
    center_r = param.Number(default=6.2, bounds=(5, 7.5))
    center_z = param.Number(default=0.545, bounds=(0, 2))
    kappa = param.Number(default=1.8, bounds=(0, 5))
    delta = param.Number(default=0.43, bounds=(0, 5))
    rx = param.Number(default=5.089, bounds=(0, 10))
    zx = param.Number(default=-3.346, bounds=(-10, 0))
    n_desired_nice_bnd_points = param.Integer(default=96, bounds=(1, 200))
