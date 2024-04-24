from dataclasses import dataclass


@dataclass
class Contact:
    name: str = None
    occupation: str = None
    url: str = None


@dataclass
class Institution:
    institution_name: str = None
    website: str = None
    industry: str = None
    type: str = None
    headquarters: str = None
    company_size: int = None
    founded: int = None


@dataclass
class Experience(Institution):
    from_date: str = None
    to_date: str = None
    description: str = None
    position_title: str = None
    location: str = None
    classification: str = None


@dataclass
class Education(Institution):
    from_date: str = None
    to_date: str = None
    description: str = None
    degree: str = None


@dataclass
class Interest(Institution):
    title = None


@dataclass
class Accomplishment(Institution):
    category = None
    title = None


