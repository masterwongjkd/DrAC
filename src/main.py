import argparse
import sys
import configparser
from DatasetReader import DatasetReader
from Annotator import Annotator
from Writer import Writer
from Vocabulary import Vocabulary
from Evaluator import Evaluator

import os
import nltk

def help(show=False):
	parser = argparse.ArgumentParser(description="")
	configs = parser.add_argument_group('System settings', 'The system parameters to run the system in the different modes')
	configs.add_argument('-s', '--settings', dest='settings', \
						type=str, default="../settings.ini", \
						help='The system settings file (default: ../settings.ini)')	

	executionMode = parser.add_argument_group('Execution Mode', 'Choose what is the execution mode!')
	executionMode.add_argument('-v', '--voc-builder', default=False, action='store_true', \
							help='In this mode, the system will create the vocabularies to use in Neju (default: False)')
	executionMode.add_argument('-a', '--annotate', default=False, action='store_true', \
							help='In this mode, the system will annotate the dataset (default: False)')
	executionMode.add_argument('-e', '--evaluate', default=False, action='store_true', \
							help='In this mode, the system will read the annotations and evaluate the dataset without converting it to \
							the matrix (default: False)')

	executionMode.add_argument('-o', '--load-ohdsi-voc', default=False, action='store_true', \
							help='In this mode, the system will load the OHDSI vocabularies into the database (default: False)')

	complementaryMode = parser.add_argument_group('Complementary functions', 'Choose the complementary functions for the execution modes!')
	complementaryMode.add_argument('-r', '--read-ann', default=False, action='store_true', \
							help='This flag is complementary to the --annotate or --evaluate execution mode. With this flag activated, \
							the system will used the neji annotations stored previously (default: False)')
	complementaryMode.add_argument('-d', '--detail-eva', default=False, action='store_true', \
							help='This flag is complementary to the --evaluate execution mode. With this flag activated, the system \
							will detail the evaluation by presenting all the false positives and negatives using the dataset (default: False)')
	
	complementaryMode.add_argument('-m', '--migrate', default=False, action='store_true', \
							help='This flag is complementary to the --annotate execution mode. With this flag activated, \
							the system will load the annotated results into the OMOP CDM Schema (default: False)')
	complementaryMode.add_argument('-l', '--load-db', default=False, action='store_true', \
							help='This flag is complementary to the --annotate execution mode and it only works if the --migrate flag is active.\
							With this flag activated, the system will load the annotated results into the database (default: False)')	
	if show:
		parser.print_help()
	return parser.parse_args()

def readSettings(settingsFile):
	configuration = configparser.ConfigParser()
	configuration.read(settingsFile)
	if not configuration:
		raise Exception("The settings file was not found!")
	return configuration._sections

def validateSettings(settings, args):
	if sum([args.voc_builder,args.annotate,args.evaluate,args.load_ohdsi_voc]) != 1:
		print("Please you only can choose one execution mode!")
		return False

	if args.voc_builder:
		if "vocabularies" not in settings:
			return False
		if 	"umls_rxnorm" not in settings["vocabularies"] or \
			"umls_drugsbank" not in settings["vocabularies"] or \
			"umls_aod" not in settings["vocabularies"] or \
			"tuis" not in settings["vocabularies"] or \
			"output" not in settings["vocabularies"]:
			return False

	if args.load_ohdsi_voc:
		if "vocabularies" not in settings:
			return False
		if "ohdsi" not in settings["vocabularies"]:
			return False

	if args.annotate or args.evaluate:
			if "dataset" not in settings or "post_vocabularies" not in settings:
				return False
			if "directory" not in settings["dataset"] or "name" not in settings["dataset"]:
				return False

	if args.load_ohdsi_voc or args.annotate:
		if "database" not in settings:
			return False
		if  "datatype" not in settings["database"] or \
			"server" not in settings["database"]  or \
			"database" not in settings["database"]  or \
			"schema" not in settings["database"]  or \
			"port" not in settings["database"]  or \
			"user" not in settings["database"]  or \
			"password" not in settings["database"] :
			return False

	if args.annotate and args.migrate:
		if "harmonisation" not in settings:
			return False
		if 	"usagi_output" not in settings["harmonisation"] or \
			"dataset" not in settings["harmonisation"]:
			return False

	return True

def vocabularyCreationMode(settings):
	print("Vocabulary creation mode!")
	vocabularies = Vocabulary.create(settings["vocabularies"])
	Writer.writeVocabularies(vocabularies, settings["vocabularies"]["output"])
	print("Done!")

def annotationMode(settings, read):
	print("Annotation mode!")
	clinicalNotes = DatasetReader.readClinicalNotes(settings["dataset"]["directory"], settings["dataset"]["name"])
	if read:
		nejiAnnotations = Annotator.readNejiAnnotations(settings["dataset"]["neji_annotations"])
	else:
		nejiAnnotations = Annotator.annotate(clinicalNotes)
		Writer.writeAnnotations(nejiAnnotations, settings["dataset"]["neji_annotations"])

	annotations = Annotator.posProcessing(clinicalNotes, nejiAnnotations, settings["post_vocabularies"])
	matrix = Writer.writeMatrix(annotations, settings["dataset"]["matrix_location"])
	print("Done!")
	return matrix

def evaluationMode(settings, read, detailEva):
	print("Evaluation mode!")
	clinicalNotes = DatasetReader.readClinicalNotes(settings["dataset"]["directory"], settings["dataset"]["name"])
	if read:
		nejiAnnotations = Annotator.readNejiAnnotations(settings["dataset"]["neji_annotations"])
	else:
		nejiAnnotations = Annotator.annotate(clinicalNotes)
	#Evaluator.evaluateNeji(clinicalNotes, nejiAnnotations, detailEva)

	annotations = Annotator.posProcessing(clinicalNotes, nejiAnnotations, settings["post_vocabularies"])
	Evaluator.evaluateAnnotations(clinicalNotes, annotations, detailEva)
	print("Done!")

def migrationMode(matrix, settings, loadIntoDB):
	print("Migration mode!")
	print("Done!")

def loadingOHDSIVocabulariesMode(settings):
	print("Loading OHDSI Vocabularies mode!")
	print("This procedure can take several minutes! Please be patient...")
	Writer.writeVocabularies(settings["database"], settings["vocabularies"]["ohdsi"])
	print("Done!")


def nltkInitialize(settings):
	nltk_dir = settings["nltk"]["nltk_dir"]
	if not os.path.exists(nltk_dir):
		nltk.download('punkt', download_dir=nltk_dir)
		print("NLTK sources downloaded to: {}".format(nltk_dir))
	nltk.data.path.append(nltk_dir)
	print("NLTK sources loaded.")


def main():
	args = help()
	settings = readSettings(args.settings)
	if validateSettings(settings, args):

		nltkInitialize(settings)

		if args.voc_builder:
			vocabularyCreationMode(settings)

		if args.annotate:
			matrix = annotationMode(settings, args.read_ann)
			if args.migrate:
				migrationMode(matrix[settings["harmonisation"]["dataset"]], settings, args.load_db)

		if args.evaluate:
			evaluationMode(settings, args.read_ann, args.detail_eva)

		if args.load_ohdsi_voc:
			loadingOHDSIVocabulariesMode(settings)
	else:
		print("The settings are not defined correctly. Please confirm all the necessary parameters in the documentation!")
		help(show=True)
		exit()

if __name__ == '__main__':
	main()