package com.github.gabrielvba.ms_producer_picture.controller;

import com.github.gabrielvba.ms_producer_picture.service.ImageService;
import com.github.gabrielvba.ms_producer_picture.service.ImageService.BinaryImageStream;
import com.github.gabrielvba.ms_producer_picture.service.ImageService.ImageNotFoundException;
import com.github.gabrielvba.ms_producer_picture.service.ImageService.CachedJsonResponse;
import jakarta.validation.constraints.Pattern;
import org.springframework.core.io.InputStreamResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/image")
@Validated
public class ImageController {

	private final ImageService imageService;

	public ImageController(ImageService imageService) {
		this.imageService = imageService;
	}

	@GetMapping(value = "/base64/{key}", produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<byte[]> getImageBase64(
			@PathVariable
			@Pattern(regexp = "^[a-zA-Z0-9._-]+$", message = "Invalid key format")
			String key) throws java.io.IOException {
		CachedJsonResponse response = imageService.getBase64Image(key);
		return ResponseEntity.ok()
				.contentLength(response.jsonBytes().length)
				.body(response.jsonBytes());
	}

	@GetMapping(value = "/raw/{key}")
	public ResponseEntity<InputStreamResource> getImageRaw(
			@PathVariable
			@Pattern(regexp = "^[a-zA-Z0-9._-]+$", message = "Invalid key format")
			String key) throws java.io.IOException {
		BinaryImageStream imageStream = imageService.getBinaryImageAsStream(key);
		HttpHeaders headers = new HttpHeaders();
		headers.setContentType(imageStream.mediaType());
		headers.setContentLength(imageStream.sizeBytes());
		if (imageStream.filename() != null) {
			headers.setContentDisposition(ContentDisposition.inline()
					.filename(imageStream.filename())
					.build());
		}

		InputStreamResource resource = new InputStreamResource(imageStream.stream());
		return new ResponseEntity<>(resource, headers, HttpStatus.OK);
	}

	@ExceptionHandler(ImageNotFoundException.class)
	public ResponseEntity<String> handleNotFound(ImageNotFoundException ex) {
		return ResponseEntity.status(HttpStatus.NOT_FOUND).body(ex.getMessage());
	}

	@ExceptionHandler(Exception.class)
	public ResponseEntity<String> handleGeneric(Exception ex) {
		return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
				.body("Error retrieving image: " + ex.getMessage());
	}
}
