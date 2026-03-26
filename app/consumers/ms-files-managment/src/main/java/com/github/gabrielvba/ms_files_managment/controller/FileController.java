package com.github.gabrielvba.ms_files_managment.controller;

import com.github.gabrielvba.ms_files_managment.service.FileService;
import com.github.gabrielvba.ms_files_managment.service.dto.ImageResponse;
import jakarta.validation.constraints.Pattern;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/file")
@Validated
public class FileController {

	private final FileService fileService;

	public FileController(FileService fileService) {
		this.fileService = fileService;
	}

	@GetMapping(value = "/base64/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<Resource> getFileAsBase64(
			@PathVariable
			@Pattern(regexp = "^[a-zA-Z0-9._-]+$", message = "Invalid id format")
			String id) {
		return fileService.getFileAsBase64Stream(id);
	}

	@GetMapping(value = "/raw/{id}", produces = MediaType.APPLICATION_OCTET_STREAM_VALUE)
	public ResponseEntity<Resource> getFileAsRaw(
			@PathVariable
			@Pattern(regexp = "^[a-zA-Z0-9._-]+$", message = "Invalid id format")
			String id) {
		return fileService.getFileAsImageStream(id);
	}
}

