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


class ShapeParams(BaseParams):
    parametric_bnd = param.Boolean(default=True)
    a = param.Number(default=1.9, bounds=(0, 5))
    center_r = param.Number(default=6.2, bounds=(5, 7.5))
    center_z = param.Number(default=0.545, bounds=(0, 2))
    kappa = param.Number(default=1.8, bounds=(0, 5))
    delta = param.Number(default=0.43, bounds=(0, 5))
    rx = param.Number(default=5.089, bounds=(0, 10))
    zx = param.Number(default=-3.346, bounds=(-10, 0))
    n_desired_nice_bnd_points = param.Integer(default=96, bounds=(1, 200))


class NiceParams(BaseParams):
    # global parameters
    mode = param.Selector(default="Inverse", objects=["Inverse"])
    iterMaxInv = param.Integer(default=40, bounds=(1, 100))
    epsStopInv = param.Number(default=1.0e-10, bounds=(1e-20, 1e-5))

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

    # @param.depends("mode", watch=True)
    # def _update_mode(self):
    #     if self.mode == "Inverse":
    #         self.param["shape_params"].precedence = 1
    #     else:
    #         self.param["shape_params"].precedence = -1
    #
    # @param.depends("mode", watch=True)
    # def _update_shape_param_visibility(self):
    #     """Update visibility of shape parameters based on parametric_bnd"""
    #     shape_params = [
    #         "a",
    #         "center_r",
    #         "center_z",
    #         "kappa",
    #         "delta",
    #         "rx",
    #         "zx",
    #         "n_desired_nice_bnd_points",
    #     ]
    #     for param_name in shape_params:
    #         if hasattr(self.param, param_name):
    #             if self.mode == "Inverse":
    #                 self.param[param_name].precedence = 1
    #             else:
    #                 # Negative precedence indicates that param should be hidden in GUI
    #                 self.param[param_name].precedence = -1
