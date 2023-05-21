from collections import defaultdict
from typing import ClassVar, Dict, List, Optional

from conda_lock.lockfile.v1.models import (
    DependencySource,
    GitMeta,
    HashModel,
    InputMeta,
    LockedDependency,
)
from conda_lock.lockfile.v1.models import Lockfile as LockfileV1
from conda_lock.lockfile.v1.models import LockMeta, MetadataOption, TimeMeta
from conda_lock.models import StrictModel


class Lockfile(StrictModel):
    version: ClassVar[int] = 2

    package: List[LockedDependency]
    metadata: LockMeta

    def __or__(self, other: "Lockfile") -> "Lockfile":
        return other.__ror__(self)

    def __ror__(self, other: "Optional[Lockfile]") -> "Lockfile":
        """
        merge self into other
        """
        if other is None:
            return self
        elif not isinstance(other, Lockfile):
            raise TypeError

        assert self.metadata.channels == other.metadata.channels

        ours = {d.key(): d for d in self.package}
        theirs = {d.key(): d for d in other.package}

        # Pick ours preferentially
        package: List[LockedDependency] = []
        for key in sorted(set(ours.keys()).union(theirs.keys())):
            if key not in ours or key[-1] not in self.metadata.platforms:
                package.append(theirs[key])
            else:
                package.append(ours[key])

        # Resort the conda packages topologically
        final_package = self._toposort(package)
        return Lockfile(package=final_package, metadata=other.metadata | self.metadata)

    def toposort_inplace(self) -> None:
        self.package = self._toposort(self.package)

    @staticmethod
    def _toposort(
        package: List[LockedDependency], update: bool = False
    ) -> List[LockedDependency]:
        platforms = {d.platform for d in package}

        # Resort the conda packages topologically
        final_package: List[LockedDependency] = []
        for platform in sorted(platforms):
            from conda_lock._vendor.conda.common.toposort import toposort

            # Add the remaining non-conda packages in the order in which they appeared.
            # Order the pip packages topologically ordered (might be not 100% perfect if they depend on
            # other conda packages, but good enough
            for manager in ["conda", "pip"]:
                lookup = defaultdict(set)
                packages: Dict[str, LockedDependency] = {}

                for d in package:
                    if d.platform != platform:
                        continue

                    if d.manager != manager:
                        continue

                    lookup[d.name] = set(d.dependencies)
                    packages[d.name] = d

                ordered = toposort(lookup)
                for package_name in ordered:
                    # since we could have a pure dep in here, that does not have a package
                    # eg a pip package that depends on a conda package (the conda package will not be in this list)
                    dep = packages.get(package_name)
                    if dep is None:
                        continue
                    if dep.manager != manager:
                        continue
                    # skip virtual packages
                    if dep.manager == "conda" and dep.name.startswith("__"):
                        continue

                    final_package.append(dep)

        return final_package

    def to_v1(self) -> LockfileV1:
        return LockfileV1(
            package=self.package,
            metadata=self.metadata,
        )


class UpdateSpecification:
    def __init__(
        self,
        locked: Optional[List[LockedDependency]] = None,
        update: Optional[List[str]] = None,
    ):
        self.locked = locked or []
        self.update = update or []


__all__ = [
    "DependencySource",
    "GitMeta",
    "HashModel",
    "InputMeta",
    "LockedDependency",
    "Lockfile",
    "LockMeta",
    "MetadataOption",
    "TimeMeta",
    "UpdateSpecification",
]
